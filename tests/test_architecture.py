"""Enforce the layer rules described in the README's Architecture section."""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1] / "src" / "mini_rag"

# Which mini_rag layers each layer may import. Web frameworks are only
# allowed in the API layer, so everything below it works without HTTP.
ALLOWED_LAYERS = {
    "api": {"api", "core", "domain", "services", "storage", "loaders", "text"},
    "services": {"core", "domain", "storage", "loaders", "text"},
    "storage": {"core", "domain"},
    "loaders": {"core", "domain"},
    "text": set(),
    "core": {"domain"},
    "domain": set(),
}
WEB_FRAMEWORKS = {"fastapi", "starlette"}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def test_every_layer_is_covered():
    layers = {path.name for path in PACKAGE.iterdir() if (path / "__init__.py").exists()}

    assert layers == set(ALLOWED_LAYERS)


@pytest.mark.parametrize("layer", sorted(ALLOWED_LAYERS))
def test_layer_imports_follow_the_rules(layer):
    violations = []
    for path in sorted((PACKAGE / layer).rglob("*.py")):
        for module in imported_modules(path):
            top, _, rest = module.partition(".")
            if top in WEB_FRAMEWORKS and layer != "api":
                violations.append(f"{path.name} imports {module}")
            if top == "mini_rag":
                target = rest.partition(".")[0]
                if target != layer and target not in ALLOWED_LAYERS[layer]:
                    violations.append(f"{path.name} imports {module}")

    assert violations == []
