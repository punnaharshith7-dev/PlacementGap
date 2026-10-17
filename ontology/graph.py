from __future__ import annotations

from collections import deque

from ontology.loader import load_edges


class SkillGraph:
    def __init__(self, prerequisites: dict[str, list[str]] | None = None) -> None:
        edges = load_edges()
        raw_prerequisites = edges["prerequisites"]
        raw_adjacent = edges["adjacent"]
        raw_specializes = edges["specializes"]
        self.prerequisites = prerequisites if prerequisites is not None else {
            str(key): list(value) for key, value in raw_prerequisites.items()
        }
        self.adjacent: dict[str, dict[str, float]] = {}
        for key, rows in raw_adjacent.items():
            self.adjacent[str(key)] = {
                str(row["skill_id"]): float(row["similarity_weight"])
                for row in rows
            }
        self.specializes: dict[str, list[str]] = {
            str(key): list(value) for key, value in raw_specializes.items()
        }
        self.dependents: dict[str, set[str]] = {}
        for skill, parents in self.prerequisites.items():
            for parent in parents:
                self.dependents.setdefault(parent, set()).add(skill)

    def traverse(self, node_id: str, depth: int = 1, edge_types: list[str] | None = None) -> dict[str, list[str]]:
        requested = set(edge_types or ["prerequisite_of", "adjacent_to", "specializes"])
        found: dict[str, list[str]] = {edge: [] for edge in requested}
        if "prerequisite_of" in requested:
            queue = deque([(node_id, 0)])
            seen = {node_id}
            while queue:
                current, level = queue.popleft()
                if level >= depth:
                    continue
                for parent in self.prerequisites.get(current, []):
                    if parent not in seen:
                        found["prerequisite_of"].append(parent)
                        seen.add(parent)
                        queue.append((parent, level + 1))
                for child in sorted(self.dependents.get(current, set())):
                    if child not in seen:
                        found["prerequisite_of"].append(child)
                        seen.add(child)
                        queue.append((child, level + 1))
        if "adjacent_to" in requested:
            found["adjacent_to"] = list(self.adjacent.get(node_id, {}))
        if "specializes" in requested:
            found["specializes"] = self.specializes.get(node_id, [])[:]
        return found

    def direct_prerequisites(self, node_id: str) -> list[str]:
        return self.prerequisites.get(node_id, [])[:]

    def is_adjacent(self, left: str, right: str) -> bool:
        return right in self.adjacent.get(left, {}) or left in self.adjacent.get(right, {})

    def adjacent_weight(self, left: str, right: str) -> float | None:
        return self.adjacent.get(left, {}).get(right) or self.adjacent.get(right, {}).get(left)

    def prerequisite_depth(self, node_id: str) -> int:
        def visit(current: str, path: set[str]) -> int:
            if current in path:
                return 0
            parents = self.prerequisites.get(current, [])
            if not parents:
                return 0
            next_path = {*path, current}
            return 1 + max((visit(parent, next_path) for parent in parents), default=0)

        return visit(node_id, set())
