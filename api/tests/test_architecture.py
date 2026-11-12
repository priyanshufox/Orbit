"""Module boundaries from docs/adr/0001-modular-monolith.md, checked on the real import graph.

Rule 2: a module's `models` and `repo` are private to that module.
Rule 3: `scoring.domain` is pure: only the standard library and itself.
Rule 4: only the `graph` module imports the Neo4j driver.

Uses grimp directly (not import-linter contracts) so rules hold even before the modules
and packages they mention exist.
"""

import sys

import grimp
import pytest

PRIVATE = {"models", "repo"}
SCORING_DOMAIN = "orbit.modules.scoring.domain"
# Third-party packages scoring.domain may use (pure maths only, e.g. "numpy").
SCORING_DOMAIN_ALLOWED_EXTERNAL: set[str] = set()
GRAPH_MODULE = "orbit.modules.graph"

# "importer -> imported" pairs allowed to break a rule, each with a reason in a comment.
ALLOWED: set[tuple[str, str]] = set()


@pytest.fixture(scope="module")
def graph() -> grimp.ImportGraph:
    return grimp.build_graph("orbit", include_external_packages=True)


def _within(module: str, package: str) -> bool:
    return module == package or module.startswith(package + ".")


def _owner(module: str) -> str | None:
    parts = module.split(".")
    return parts[2] if parts[:2] == ["orbit", "modules"] and len(parts) > 2 else None


def _imports(graph: grimp.ImportGraph):
    for importer in sorted(graph.modules):
        if not _within(importer, "orbit"):
            continue
        for imported in sorted(graph.find_modules_directly_imported_by(importer)):
            if (importer, imported) not in ALLOWED:
                yield importer, imported


def rule2_violations(graph: grimp.ImportGraph) -> list[str]:
    out = []
    for importer, imported in _imports(graph):
        parts = imported.split(".")
        is_private = parts[:2] == ["orbit", "modules"] and len(parts) > 3 and parts[3] in PRIVATE
        if is_private and _owner(importer) != parts[2]:
            out.append(f"{importer} -> {imported}")
    return out


def rule3_violations(graph: grimp.ImportGraph) -> list[str]:
    out = []
    for importer, imported in _imports(graph):
        if not _within(importer, SCORING_DOMAIN) or _within(imported, SCORING_DOMAIN):
            continue
        top = imported.split(".")[0]
        if top in sys.stdlib_module_names or top in SCORING_DOMAIN_ALLOWED_EXTERNAL:
            continue
        out.append(f"{importer} -> {imported}")
    return out


def rule4_violations(graph: grimp.ImportGraph) -> list[str]:
    return [
        f"{importer} -> {imported}"
        for importer, imported in _imports(graph)
        if imported.split(".")[0] == "neo4j" and not _within(importer, GRAPH_MODULE)
    ]


def _fail_message(advice: str, violations: list[str]) -> str:
    return advice + ":\n  " + "\n  ".join(violations)


def test_rule2_models_and_repo_are_private(graph: grimp.ImportGraph) -> None:
    v = rule2_violations(graph)
    assert not v, _fail_message("Call the owning module's service, not its models/repo", v)


def test_rule3_scoring_domain_is_pure(graph: grimp.ImportGraph) -> None:
    v = rule3_violations(graph)
    assert not v, _fail_message("Pass data into scoring.domain; do I/O in scoring's job", v)


def test_rule4_only_graph_talks_to_neo4j(graph: grimp.ImportGraph) -> None:
    v = rule4_violations(graph)
    assert not v, _fail_message("Go through the graph module's service", v)
