from __future__ import annotations

import os
from pathlib import Path

import yaml


class ModelRouter:
    def __init__(self, config_path: Path | None = None, override: str | None = None) -> None:
        self.path = config_path or Path(__file__).parents[1] / "config" / "models.yaml"
        self.config = yaml.safe_load(self.path.read_text(encoding="utf-8"))
        self.override = override or os.getenv("PLACEMENTGAP_MODEL_OVERRIDE")

    def model_for(self, node_name: str, *, stronger: bool = False) -> str:
        if self.override:
            return self.override
        if os.getenv("PLACEMENTGAP_ABLATION") == "cheap_model_only":
            return str(self.config["defaults"]["cheap"])
        tier = self.config.get("nodes", {}).get(node_name, "cheap")
        if stronger:
            tier = "strong"
        return str(self.config["defaults"][tier])

    def prices(self, model: str) -> tuple[float, float]:
        prices = self.config.get("prices_per_million_tokens", {}).get(model, {})
        return float(prices.get("input", 0)), float(prices.get("output", 0))

