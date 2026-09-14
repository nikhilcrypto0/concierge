"""Split help-center markdown into heading-scoped chunks.

One "## " section per chunk keeps each chunk about one topic, which is what makes
Recall@k meaningful. Oversized sections are split on paragraph boundaries.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

MAX_CHUNK_CHARS = 1_200
_SECTION = re.compile(r"^##\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    id: str
    doc_slug: str
    doc_title: str
    heading: str
    content: str

    @property
    def content_hash(self) -> str:
        payload = f"{self.doc_title}\n{self.heading}\n{self.content}".encode()
        return hashlib.sha256(payload).hexdigest()

    @property
    def embedding_text(self) -> str:
        return f"{self.doc_title} - {self.heading}\n{self.content}"


def _split_paragraphs(text: str, limit: int) -> list[str]:
    parts: list[str] = []
    current = ""
    for para in (p.strip() for p in text.split("\n\n")):
        if not para:
            continue
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= limit or not current:
            current = candidate
        else:
            parts.append(current)
            current = para
    if current:
        parts.append(current)
    return parts


def chunk_markdown(slug: str, markdown: str, max_chars: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    title_match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    if not title_match:
        raise ValueError(f"{slug}: document must start with a '# Title' line")
    title = title_match.group(1).strip()

    matches = list(_SECTION.finditer(markdown))
    sections: list[tuple[str, str]] = []
    intro = markdown[title_match.end() : matches[0].start() if matches else len(markdown)]
    if intro.strip():
        sections.append(("Overview", intro))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        sections.append((match.group(1).strip(), markdown[match.end() : end]))

    chunks: list[Chunk] = []
    for heading, body in sections:
        for part in _split_paragraphs(body, max_chars):
            chunks.append(Chunk(f"{slug}#{len(chunks)}", slug, title, heading, part))
    return chunks


def load_directory(directory: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(directory.glob("*.md")):
        chunks.extend(chunk_markdown(path.stem, path.read_text()))
    return chunks
