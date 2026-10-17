from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import os
import re
import socket
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, ConfigDict


class FetchedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    text: str
    content_hash: str
    status_code: int
    cache_hit: bool = False


_CACHE: dict[str, FetchedPage] = {}
_USER_AGENT = "PlacementGapResearchBot/1.0 (+https://localhost; respects robots.txt)"


def _disk_cache_path() -> Path:
    return Path(os.getenv("PLACEMENTGAP_FETCH_CACHE", "./data/fetch_cache.sqlite3"))


def _disk_read(cache_key: str) -> FetchedPage | None:
    path = _disk_cache_path()
    if not path.exists():
        return None
    with sqlite3.connect(path, timeout=5) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS fetched_pages (cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, cached_at TEXT NOT NULL)")
        row = connection.execute("SELECT payload,cached_at FROM fetched_pages WHERE cache_key=?", (cache_key,)).fetchone()
    if not row:
        return None
    try:
        cached_at = datetime.fromisoformat(row[1])
    except ValueError:
        return None
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=UTC)
    if cached_at < datetime.now(UTC) - timedelta(days=14):
        return None
    return FetchedPage.model_validate_json(row[0]).model_copy(update={"cache_hit": True})


def _disk_write(cache_key: str, result: FetchedPage) -> None:
    path = _disk_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=5) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS fetched_pages (cache_key TEXT PRIMARY KEY, payload TEXT NOT NULL, cached_at TEXT NOT NULL)")
        connection.execute(
            "INSERT OR REPLACE INTO fetched_pages(cache_key,payload,cached_at) VALUES(?,?,?)",
            (cache_key, result.model_dump_json(), datetime.now(UTC).isoformat()),
        )
        connection.commit()


async def _resolve_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise ValueError("Only absolute HTTP(S) URLs are accepted")
    host = parsed.hostname.casefold()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Localhost and local network URLs are not accepted")
    try:
        addresses = await asyncio.to_thread(socket.getaddrinfo, host, parsed.port or (443 if parsed.scheme == "https" else 80))
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if not ip.is_global:
                raise ValueError("Private and non-public network addresses are not accepted")
    except socket.gaierror:
        raise ValueError("Could not resolve the requested hostname") from None
    return urlunparse(parsed._replace(fragment=""))


async def fetch_url(url: str, timeout_s: float = 15.0) -> FetchedPage:
    normalized = await _resolve_public_url(url)
    if normalized in _CACHE:
        return _CACHE[normalized].model_copy(update={"cache_hit": True})
    cache_key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    cached = await asyncio.to_thread(_disk_read, cache_key)
    if cached:
        _CACHE[normalized] = cached
        return cached
    current_url = normalized
    timeout = httpx.Timeout(timeout_s)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers={"User-Agent": _USER_AGENT}) as client:
        response: httpx.Response | None = None
        for _ in range(6):
            parsed = urlparse(current_url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
            try:
                robots_response = await client.get(robots_url)
                parser = RobotFileParser(robots_url)
                parser.parse(robots_response.text.splitlines() if robots_response.status_code < 400 else [])
                if not parser.can_fetch(_USER_AGENT, current_url):
                    raise PermissionError("robots.txt disallows fetching this URL")
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Could not verify robots.txt: {exc}") from exc
            response = await client.get(current_url)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Redirect response did not include a location")
                current_url = await _resolve_public_url(urljoin(current_url, location))
                continue
            break
        if response is None or response.is_redirect:
            raise ValueError("URL exceeded the redirect limit")
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        element.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()
    if not text:
        raise ValueError("The fetched page did not contain readable text")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    result = FetchedPage(url=current_url, text=text[:250_000], content_hash=digest, status_code=response.status_code)
    _CACHE[normalized] = result
    await asyncio.to_thread(_disk_write, cache_key, result)
    return result
