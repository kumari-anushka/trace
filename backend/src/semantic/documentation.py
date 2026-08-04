from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Protocol
from urllib.parse import quote
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.github.models import SourceFile, SourceFileContent
from src.graph.models import GraphNode
from src.repositories.models import Repository
from src.repository_versions.models import RepositoryVersion
from src.semantic.models import DocumentSourceType
from src.semantic.repository import DocumentInput, SemanticRepository

DOCUMENTATION_CHUNKER_VERSION = "documentation-v1"
MAX_DOCUMENT_CHUNK_CHARS = 2_400
TARGET_DOCUMENT_CHUNK_CHARS = 1_600
MIN_DOCUMENT_CHUNK_CHARS = 600

_MARKDOWN_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_ASCIIDOC_HEADING = re.compile(r"^\s*={1,6}\s+(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class DocumentationSourceInput:
    id: UUID
    path: str
    blob_sha: str
    content: str
    content_hash: str
    source_url: str
    source_node_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class DocumentationChunk:
    content: str
    start_offset: int
    end_offset: int
    start_line: int
    end_line: int
    heading: str | None


@dataclass(frozen=True, slots=True)
class DocumentationChunkSummary:
    files: int
    chunks: int
    characters: int
    empty_files: int
    stale_documents: int
    chunker_version: str = DOCUMENTATION_CHUNKER_VERSION


class DocumentationSourceReader(Protocol):
    async def list_documentation_sources(
        self, repository_version_id: UUID
    ) -> Sequence[DocumentationSourceInput]: ...


class PostgresDocumentationSourceReader:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def list_documentation_sources(
        self, repository_version_id: UUID
    ) -> Sequence[DocumentationSourceInput]:
        rows = await self.session.execute(
            select(
                SourceFile,
                SourceFileContent.content,
                SourceFileContent.content_hash,
                Repository.github_url,
                RepositoryVersion.commit_sha,
            )
            .join(SourceFileContent, SourceFileContent.source_file_id == SourceFile.id)
            .join(
                RepositoryVersion,
                RepositoryVersion.id == SourceFile.repository_version_id,
            )
            .join(Repository, Repository.id == RepositoryVersion.repository_id)
            .where(
                SourceFile.repository_version_id == repository_version_id,
                SourceFile.file_kind == "documentation",
            )
            .order_by(SourceFile.path)
        )
        graph_rows = await self.session.execute(
            select(GraphNode.id, GraphNode.details).where(
                GraphNode.repository_version_id == repository_version_id,
                GraphNode.entity_type == "file",
            )
        )
        node_ids_by_path = {
            path: node_id
            for node_id, metadata in graph_rows.all()
            if isinstance((path := metadata.get("path")), str)
        }

        return [
            DocumentationSourceInput(
                id=source_file.id,
                path=source_file.path,
                blob_sha=source_file.blob_sha,
                content=content,
                content_hash=content_hash,
                source_url=_source_url(github_url, commit_sha, source_file.path),
                source_node_id=node_ids_by_path.get(source_file.path),
            )
            for source_file, content, content_hash, github_url, commit_sha in rows.all()
        ]


class DocumentationChunkBuilder:
    def __init__(
        self,
        *,
        semantic_repository: SemanticRepository,
        source_reader: DocumentationSourceReader,
    ) -> None:
        self.semantic_repository = semantic_repository
        self.source_reader = source_reader

    async def build(
        self,
        *,
        repository_id: UUID,
        repository_version_id: UUID,
    ) -> DocumentationChunkSummary:
        sources = await self.source_reader.list_documentation_sources(repository_version_id)
        retained_keys: list[str] = []
        chunk_count = 0
        character_count = 0
        empty_files = 0

        for source in sorted(sources, key=lambda item: item.path):
            chunks = chunk_documentation(source.content)
            if not chunks:
                empty_files += 1
                continue
            for chunk_index, chunk in enumerate(chunks):
                canonical_key = _document_key(
                    repository_id=repository_id,
                    repository_version_id=repository_version_id,
                    path=source.path,
                    chunk_index=chunk_index,
                )
                retained_keys.append(canonical_key)
                await self.semantic_repository.upsert_document(
                    DocumentInput(
                        repository_id=repository_id,
                        repository_version_id=repository_version_id,
                        source_node_id=source.source_node_id,
                        source_type=DocumentSourceType.REPOSITORY_DOCUMENTATION,
                        source_key=source.path,
                        canonical_key=canonical_key,
                        title=chunk.heading or PurePosixPath(source.path).name,
                        content=chunk.content,
                        chunk_index=chunk_index,
                        start_offset=chunk.start_offset,
                        end_offset=chunk.end_offset,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        source_url=source.source_url,
                        provenance={
                            "kind": "source_chunk",
                            "provider": "github_archive",
                            "chunker": DOCUMENTATION_CHUNKER_VERSION,
                            "source_file_id": str(source.id),
                            "source_content_hash": source.content_hash,
                        },
                        metadata={
                            "path": source.path,
                            "blob_sha": source.blob_sha,
                            "source_content_hash": source.content_hash,
                            "chunker_version": DOCUMENTATION_CHUNKER_VERSION,
                            "heading": chunk.heading,
                            "start_line": chunk.start_line,
                            "end_line": chunk.end_line,
                            "start_offset": chunk.start_offset,
                            "end_offset": chunk.end_offset,
                        },
                    )
                )
                chunk_count += 1
                character_count += len(chunk.content)

        stale_documents = await self.semantic_repository.prune_documents(
            repository_id=repository_id,
            repository_version_id=repository_version_id,
            source_type=DocumentSourceType.REPOSITORY_DOCUMENTATION,
            retained_canonical_keys=retained_keys,
        )
        return DocumentationChunkSummary(
            files=len(sources),
            chunks=chunk_count,
            characters=character_count,
            empty_files=empty_files,
            stale_documents=stale_documents,
        )


def chunk_documentation(content: str) -> tuple[DocumentationChunk, ...]:
    if not content.strip():
        return ()

    raw_spans: list[tuple[int, int]] = []
    current_start: int | None = None
    offset = 0
    for line in content.splitlines(keepends=True):
        line_start = offset
        line_end = line_start + len(line)
        is_heading = _heading_text(line) is not None
        if (
            current_start is not None
            and is_heading
            and line_start - current_start >= MIN_DOCUMENT_CHUNK_CHARS
        ):
            raw_spans.append((current_start, line_start))
            current_start = None
        if current_start is None:
            current_start = line_start
        while line_end - current_start > MAX_DOCUMENT_CHUNK_CHARS:
            maximum_end = current_start + MAX_DOCUMENT_CHUNK_CHARS
            chunk_end = _preferred_break(content, current_start, maximum_end)
            raw_spans.append((current_start, chunk_end))
            current_start = chunk_end
        if line.strip() == "" and line_end - current_start >= TARGET_DOCUMENT_CHUNK_CHARS:
            raw_spans.append((current_start, line_end))
            current_start = None
        offset = line_end

    if offset < len(content):
        if current_start is None:
            current_start = offset
        line_end = len(content)
        while line_end - current_start > MAX_DOCUMENT_CHUNK_CHARS:
            maximum_end = current_start + MAX_DOCUMENT_CHUNK_CHARS
            chunk_end = _preferred_break(content, current_start, maximum_end)
            raw_spans.append((current_start, chunk_end))
            current_start = chunk_end
        offset = line_end
    if current_start is not None and current_start < offset:
        raw_spans.append((current_start, offset))

    heading_positions = _heading_positions(content)
    chunks: list[DocumentationChunk] = []
    for raw_start, raw_end in raw_spans:
        start, end = _trim_span(content, raw_start, raw_end)
        if start >= end:
            continue
        chunks.append(
            DocumentationChunk(
                content=content[start:end],
                start_offset=start,
                end_offset=end,
                start_line=_start_line(content, start),
                end_line=_end_line(content, start, end),
                heading=_heading_for_offset(heading_positions, start),
            )
        )
    return tuple(chunks)


def _preferred_break(content: str, start: int, maximum_end: int) -> int:
    minimum_end = min(start + MIN_DOCUMENT_CHUNK_CHARS, maximum_end)
    paragraph_break = content.rfind("\n\n", minimum_end, maximum_end)
    if paragraph_break >= minimum_end:
        return paragraph_break + 2
    line_break = content.rfind("\n", minimum_end, maximum_end)
    if line_break >= minimum_end:
        return line_break + 1
    whitespace = max(
        content.rfind(" ", minimum_end, maximum_end),
        content.rfind("\t", minimum_end, maximum_end),
    )
    return whitespace + 1 if whitespace >= minimum_end else maximum_end


def _trim_span(content: str, start: int, end: int) -> tuple[int, int]:
    while start < end and content[start].isspace():
        start += 1
    while end > start and content[end - 1].isspace():
        end -= 1
    return start, end


def _heading_positions(content: str) -> tuple[tuple[int, str], ...]:
    headings: list[tuple[int, str]] = []
    offset = 0
    for line in content.splitlines(keepends=True):
        heading = _heading_text(line)
        if heading is not None:
            headings.append((offset, heading))
        offset += len(line)
    return tuple(headings)


def _heading_text(line: str) -> str | None:
    value = line.rstrip("\r\n")
    match = _MARKDOWN_HEADING.match(value) or _ASCIIDOC_HEADING.match(value)
    return match.group(1).strip() if match else None


def _heading_for_offset(headings: Sequence[tuple[int, str]], offset: int) -> str | None:
    heading: str | None = None
    for heading_offset, value in headings:
        if heading_offset > offset:
            break
        heading = value
    return heading


def _start_line(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def _end_line(content: str, start: int, end: int) -> int:
    newline_count = content.count("\n", 0, end)
    return newline_count if end > start and content[end - 1] == "\n" else newline_count + 1


def _document_key(
    *,
    repository_id: UUID,
    repository_version_id: UUID,
    path: str,
    chunk_index: int,
) -> str:
    identity = f"{path}\0{chunk_index}\0{DOCUMENTATION_CHUNKER_VERSION}"
    digest = sha256(identity.encode()).hexdigest()
    return f"repo:{repository_id}:snapshot:{repository_version_id}:documentation-chunk:{digest}"


def _source_url(github_url: str, commit_sha: str, path: str) -> str:
    encoded_path = quote(path, safe="/")
    return f"{github_url.rstrip('/')}/blob/{commit_sha}/{encoded_path}"
