from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

import pytest

from src.github.classification import (
    classify_source_file,
    extract_text_files_from_zip,
    normalize_repository_path,
)
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


def make_archive(files: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for path, content in files.items():
            archive.writestr(f"acme-trace/{path}", content)
    return buffer.getvalue()


def test_extracts_normalized_text_with_sha256_hash() -> None:
    extraction = extract_text_files_from_zip(
        make_archive({"src/main.py": b"print('trace')\r\n"}),
        allowed_paths={"src/main.py"},
        max_file_bytes=1_000,
    )

    assert len(extraction.files) == 1
    extracted = extraction.files[0]
    assert extracted.path == "src/main.py"
    assert extracted.content == "print('trace')\n"
    assert extracted.content_hash == sha256(b"print('trace')\n").hexdigest()
    assert extracted.line_count == 1


def test_archive_extraction_reports_large_binary_and_missing_files() -> None:
    extraction = extract_text_files_from_zip(
        make_archive(
            {
                "large.py": b"x" * 11,
                "binary.py": b"abc\x00def",
            }
        ),
        allowed_paths={"large.py", "binary.py", "missing.py"},
        max_file_bytes=10,
    )

    assert extraction.files == []
    assert extraction.skipped_large == 1
    assert extraction.skipped_non_text == 1
    assert extraction.missing == 1


def test_rejects_invalid_zip_archive() -> None:
    with pytest.raises(ValueError, match="invalid repository archive"):
        extract_text_files_from_zip(
            b"not-a-zip",
            allowed_paths={"src/main.py"},
            max_file_bytes=1_000,
        )
