"""Louvain communities in Python (task 6.4 fallback when Neo4j GDS isn't available)."""

from collections.abc import Iterable
from uuid import UUID

import networkx as nx


def louvain(people: Iterable[UUID], edges: Iterable[tuple[UUID, UUID, float]]) -> dict[UUID, int]:
    graph = nx.Graph()
    graph.add_nodes_from(str(p) for p in people)
    graph.add_weighted_edges_from((str(a), str(b), max(w, 1e-6)) for a, b, w in edges)
    communities = nx.community.louvain_communities(graph, weight="weight", seed=42)
    return relabel({UUID(n): i for i, members in enumerate(communities) for n in members})


def relabel(assignment: dict[UUID, int]) -> dict[UUID, int]:
    """Stable labels 0..k-1, biggest community first, ties by smallest member id. Same input,
    same colours, whichever algorithm produced the communities."""
    groups: dict[int, list[UUID]] = {}
    for person, community in assignment.items():
        groups.setdefault(community, []).append(person)
    ordered = sorted(groups.values(), key=lambda m: (-len(m), min(str(x) for x in m)))
    return {person: label for label, members in enumerate(ordered) for person in members}
