from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from src.github.models import SourceFileKind

IGNORED_PARTS = {
    ".git",
    ".idea",
    ".next",
    ".tox",
    ".venv",
    ".vscode",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "vendor",
}
BINARY_SUFFIXES = {
    ".7z",
    ".avi",
    ".class",
    ".dll",
    ".dylib",
    ".eot",
    ".exe",
    ".gif",
    ".gz",
    ".ico",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lockb",
    ".mov",
    ".mp3",
    ".mp4",
    ".otf",
    ".pdf",
    ".png",
    ".pyc",
    ".so",
    ".tar",
    ".ttf",
    ".webm",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
}
DOCUMENTATION_SUFFIXES = {".md", ".mdx", ".rst", ".txt", ".adoc"}
GENERATED_NAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "poetry.lock",
    "cargo.lock",
}
SOURCE_LANGUAGES = {
    ".py": "Python",
    ".pyi": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".json": "JSON",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".sql": "SQL",
    ".sh": "Shell",
    ".css": "CSS",
    ".scss": "SCSS",
    ".html": "HTML",
}


@dataclass(frozen=True, slots=True)
class ArchiveTextFile:
    path: str
    content: str
    content_hash: str
    encoding: str
    byte_size: int
    line_count: int


@dataclass(frozen=True, slots=True)
class ArchiveExtraction:
    files: list[ArchiveTextFile]
    skipped_large: int
    skipped_non_text: int
    missing: int


def normalize_repository_path(path: str) -> str:
    normalized = PurePosixPath(path)
    if normalized.is_absolute() or not normalized.parts or ".." in normalized.parts:
        raise ValueError(f"Unsafe repository path: {path}")
    return normalized.as_posix().removeprefix("./")


def classify_source_file(path: str) -> tuple[SourceFileKind, str | None]:
    normalized = PurePosixPath(normalize_repository_path(path))
    parts = {part.lower() for part in normalized.parts}
    name = normalized.name.lower()
    suffix = normalized.suffix.lower()

    if parts & IGNORED_PARTS:
        return SourceFileKind.IGNORED, SOURCE_LANGUAGES.get(suffix)
    if suffix in BINARY_SUFFIXES:
        return SourceFileKind.BINARY, None
    if name in GENERATED_NAMES or name.endswith((".min.js", ".min.css", ".generated.ts")):
        return SourceFileKind.GENERATED, SOURCE_LANGUAGES.get(suffix)
    if suffix in DOCUMENTATION_SUFFIXES or name in {"license", "readme", "changelog"}:
        return SourceFileKind.DOCUMENTATION, None
    if (
        "test" in parts
        or "tests" in parts
        or "__tests__" in parts
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    ):
        return SourceFileKind.TEST, SOURCE_LANGUAGES.get(suffix)
    return SourceFileKind.SOURCE, SOURCE_LANGUAGES.get(suffix)


def extract_text_files_from_zip(
    archive: bytes,
    *,
    allowed_paths: set[str],
    max_file_bytes: int,
) -> ArchiveExtraction:
    extracted: list[ArchiveTextFile] = []
    skipped_large = 0
    skipped_non_text = 0
    seen: set[str] = set()

    try:
        zip_file = ZipFile(BytesIO(archive))
    except BadZipFile as error:
        raise ValueError("GitHub returned an invalid repository archive") from error

    with zip_file:
        for entry in zip_file.infolist():
            if entry.is_dir():
                continue
            parts = PurePosixPath(entry.filename).parts
            if len(parts) < 2:
                continue
            path = normalize_repository_path(PurePosixPath(*parts[1:]).as_posix())
            if path not in allowed_paths:
                continue
            seen.add(path)
            if entry.file_size > max_file_bytes:
                skipped_large += 1
                continue
            raw_content = zip_file.read(entry)
            if b"\x00" in raw_content:
                skipped_non_text += 1
                continue
            try:
                decoded = raw_content.decode("utf-8-sig")
            except UnicodeDecodeError:
                skipped_non_text += 1
                continue
            normalized_content = decoded.replace("\r\n", "\n").replace("\r", "\n")
            normalized_bytes = normalized_content.encode("utf-8")
            extracted.append(
                ArchiveTextFile(
                    path=path,
                    content=normalized_content,
                    content_hash=sha256(normalized_bytes).hexdigest(),
                    encoding="utf-8",
                    byte_size=len(normalized_bytes),
                    line_count=(
                        normalized_content.count("\n")
                        + (1 if normalized_content and not normalized_content.endswith("\n") else 0)
                    ),
                )
            )

    return ArchiveExtraction(
        files=extracted,
        skipped_large=skipped_large,
        skipped_non_text=skipped_non_text,
        missing=len(allowed_paths - seen),
    )
