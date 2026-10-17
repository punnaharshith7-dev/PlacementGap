from __future__ import annotations

from ontology.graph import SkillGraph


def search_skill_graph(
    node_id: str, depth: int = 1, edge_types: list[str] | None = None
) -> dict[str, list[str]]:
    return SkillGraph().traverse(node_id, depth=depth, edge_types=edge_types)
