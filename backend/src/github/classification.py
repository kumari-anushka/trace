from pathlib import PurePosixPath

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
