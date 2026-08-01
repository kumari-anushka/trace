import pytest

from src.github.classification import classify_source_file, normalize_repository_path
from src.github.models import SourceFileKind


@pytest.mark.parametrize(
    ("path", "expected_kind", "expected_language"),
    [
        ("src/main.py", SourceFileKind.SOURCE, "Python"),
        ("tests/test_main.py", SourceFileKind.TEST, "Python"),
        ("frontend/Button.spec.tsx", SourceFileKind.TEST, "TypeScript"),
        ("docs/architecture.md", SourceFileKind.DOCUMENTATION, None),
        ("public/logo.png", SourceFileKind.BINARY, None),
        ("frontend/package-lock.json", SourceFileKind.GENERATED, "JSON"),
        ("node_modules/pkg/index.js", SourceFileKind.IGNORED, "JavaScript"),
    ],
)
def test_classifies_source_tree_entries(
    path: str,
    expected_kind: SourceFileKind,
    expected_language: str | None,
) -> None:
    assert classify_source_file(path) == (expected_kind, expected_language)


@pytest.mark.parametrize("path", ["/etc/passwd", "../secret", "src/../../secret"])
def test_rejects_unsafe_repository_paths(path: str) -> None:
    with pytest.raises(ValueError, match="Unsafe repository path"):
        normalize_repository_path(path)
