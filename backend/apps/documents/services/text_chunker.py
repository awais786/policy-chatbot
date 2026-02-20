"""
Text chunking service with FAQ-aware grouping.

Pipeline:
  1. Regex preprocessing (normalize whitespace, quotes, hyphens)
  2. Detect document style: FAQ (numbered Q&A) vs prose
  3. For FAQ docs  → group each Q&A pair as an atomic unit
     For prose docs → split into topical sections by heading
  4. Split groups that exceed chunk_size using RecursiveCharacterTextSplitter
  5. Merge adjacent chunks that are too small (< min_chunk_size)
  6. Optional spaCy sentence-boundary pre-pass
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    LANGCHAIN_AVAILABLE = True
except ImportError:
    RecursiveCharacterTextSplitter = None
    LANGCHAIN_AVAILABLE = False

try:
    import spacy

    try:
        _nlp = spacy.load("en_core_web_sm")
        SPACY_MODEL_AVAILABLE = True
    except OSError:
        _nlp = None
        SPACY_MODEL_AVAILABLE = False
except ImportError:
    spacy = None
    _nlp = None
    SPACY_MODEL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Regex patterns compiled once
# ---------------------------------------------------------------------------

_QA_NUMBER_RE = re.compile(
    r"^\s*(?:"
    r"\d{1,3}[\.\)]\s+"          # 1. or 1)
    r"|[a-zA-Z][\.\)]\s+"        # a. or a)
    r"|Q\d*[\.:]\s*"             # Q: or Q1:
    r"|Question\s*\d*[\.:]\s*"   # Question: or Question 1:
    r")",
    re.IGNORECASE,
)

_HEADING_PATTERNS = (
    re.compile(r"^[A-Z][A-Za-z0-9&/,\- ]{3,80}$"),
    re.compile(r"^\d+[\.\)]\s+[A-Z][A-Za-z0-9&/,\- ]{3,80}$"),
)

_MIN_CHUNK_CHARS = 200


@dataclass
class TextChunk:
    content: str
    chunk_index: int
    metadata: Dict[str, Any]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
    preserve_sentences: bool = True,
) -> List[TextChunk]:
    """Chunk text for embeddings, keeping Q&A pairs together."""
    if not text or not text.strip():
        return []

    chunk_size = int(chunk_size or getattr(settings, "CHUNK_SIZE", 1000))
    chunk_overlap = int(chunk_overlap or getattr(settings, "CHUNK_OVERLAP", 200))
    chunk_overlap = max(0, min(chunk_overlap, chunk_size - 1))

    normalized = preprocess_text(text)

    if _is_faq_document(normalized):
        groups = _split_faq_pairs(normalized)
        doc_style = "faq"
    else:
        groups = _split_sections(normalized)
        doc_style = "prose"

    all_chunks: List[TextChunk] = []
    chunk_index = 0

    for group_title, group_text in groups:
        group_text = group_text.strip()
        if not group_text:
            continue

        if preserve_sentences and SPACY_MODEL_AVAILABLE:
            group_text = _sentence_preserve_prepass(group_text)

        if len(group_text) <= chunk_size:
            raw_chunks = [group_text]
        elif LANGCHAIN_AVAILABLE:
            raw_chunks = _chunk_with_recursive_splitter(
                group_text, chunk_size, chunk_overlap
            )
        else:
            raw_chunks = _chunk_with_fallback(group_text, chunk_size, chunk_overlap)

        for local_index, chunk in enumerate(raw_chunks):
            if not chunk or not chunk.strip():
                continue
            all_chunks.append(
                TextChunk(
                    content=chunk,
                    chunk_index=chunk_index,
                    metadata={
                        "chunk_method": "recursive",
                        "doc_style": doc_style,
                        "spacy_preserved": bool(
                            preserve_sentences and SPACY_MODEL_AVAILABLE
                        ),
                        "section_title": group_title,
                        "section_chunk_index": local_index,
                    },
                )
            )
            chunk_index += 1

    all_chunks = _merge_small_chunks(all_chunks, chunk_size)
    return all_chunks


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------


def preprocess_text(text: str) -> str:
    """Regex-based normalization before splitting."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\u201c|\u201d", '"', text)
    text = re.sub(r"\u2018|\u2019|\u0060", "'", text)
    text = re.sub(r"\u2013|\u2014", "-", text)
    return text.strip()


# ---------------------------------------------------------------------------
# FAQ detection and splitting
# ---------------------------------------------------------------------------


def _is_faq_document(text: str) -> bool:
    """
    Heuristic: if >= 3 lines match a numbered-question pattern,
    treat the whole document as FAQ-style.
    """
    lines = text.split("\n")
    qa_hits = sum(1 for ln in lines if _QA_NUMBER_RE.match(ln.strip()))
    return qa_hits >= 3


def _split_faq_pairs(text: str) -> List[Tuple[str, str]]:
    """
    Split FAQ text so each numbered Q&A pair stays together as one group.

    Input:
        1. Why do females get travel allowance?
        Because females face different challenges...
        their travel allowance reflects this.

        2. Why isn't salary reviewed quarterly?
        Everyone is reviewed on their annual anniversary...

    Output:
        [
          ("Q1", "1. Why do females get travel allowance?\nBecause females..."),
          ("Q2", "2. Why isn't salary reviewed quarterly?\nEveryone is..."),
        ]
    """
    lines = text.split("\n")
    pairs: List[Tuple[str, List[str]]] = []
    current_lines: List[str] = []
    pair_count = 0

    for line in lines:
        stripped = line.strip()

        if _QA_NUMBER_RE.match(stripped) and current_lines:
            pair_count += 1
            pairs.append((f"Q{pair_count}", current_lines))
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        pair_count += 1
        pairs.append((f"Q{pair_count}", current_lines))

    return [
        (title, "\n".join(body).strip())
        for title, body in pairs
        if any(ln.strip() for ln in body)
    ]


# ---------------------------------------------------------------------------
# Prose section splitting (non-FAQ documents)
# ---------------------------------------------------------------------------


def _split_sections(text: str) -> List[Tuple[str, str]]:
    """Split prose documents into topical sections by heading."""
    lines = text.split("\n")
    sections: List[Tuple[str, List[str]]] = []
    current_title = "General"
    current_lines: List[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            current_lines.append("")
            continue

        if _looks_like_heading(line):
            if any(ln.strip() for ln in current_lines):
                sections.append((current_title, current_lines))
            current_title = line
            current_lines = []
            continue

        current_lines.append(raw_line)

    if any(ln.strip() for ln in current_lines):
        sections.append((current_title, current_lines))

    if not sections:
        return [("General", text)]

    return [(title, "\n".join(body).strip()) for title, body in sections]


def _looks_like_heading(line: str) -> bool:
    """Heuristic for detecting section headings in prose documents."""
    if len(line) < 4 or len(line) > 90:
        return False
    if line.endswith(("?", ".", ",", ";", ":")):
        return False
    return any(pat.match(line) for pat in _HEADING_PATTERNS)


# ---------------------------------------------------------------------------
# Small-chunk merging
# ---------------------------------------------------------------------------


def _merge_small_chunks(
    chunks: List[TextChunk], chunk_size: int
) -> List[TextChunk]:
    """
    Merge adjacent chunks that are under _MIN_CHUNK_CHARS into their
    neighbour, as long as the combined size stays within chunk_size.
    """
    if len(chunks) <= 1:
        return chunks

    merged: List[TextChunk] = [chunks[0]]

    for chunk in chunks[1:]:
        prev = merged[-1]
        combined_len = len(prev.content) + len(chunk.content) + 2

        can_merge = (
            len(prev.content) < _MIN_CHUNK_CHARS
            or len(chunk.content) < _MIN_CHUNK_CHARS
        )

        if can_merge and combined_len <= chunk_size:
            merged[-1] = TextChunk(
                content=prev.content + "\n\n" + chunk.content,
                chunk_index=prev.chunk_index,
                metadata={
                    **prev.metadata,
                    "merged": True,
                },
            )
        else:
            merged.append(chunk)

    for i, chunk in enumerate(merged):
        chunk.chunk_index = i

    return merged


# ---------------------------------------------------------------------------
# Splitting backends
# ---------------------------------------------------------------------------


def _sentence_preserve_prepass(text: str) -> str:
    """
    spaCy pre-pass: one sentence per line so the splitter avoids
    cutting sentences in half.
    """
    if not SPACY_MODEL_AVAILABLE or _nlp is None:
        return text
    try:
        doc = _nlp(text)
        sents = [s.text.strip() for s in doc.sents if s.text.strip()]
        return "\n".join(sents) if sents else text
    except Exception as exc:
        logger.warning("spaCy sentence pre-pass failed: %s", exc)
        return text


def _chunk_with_recursive_splitter(
    text: str, chunk_size: int, chunk_overlap: int
) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
        keep_separator=True,
    )
    return [c.strip() for c in splitter.split_text(text) if c and c.strip()]


def _chunk_with_fallback(
    text: str, chunk_size: int, chunk_overlap: int
) -> List[str]:
    """Simple deterministic fallback splitter."""
    if len(text) <= chunk_size:
        return [text.strip()]

    chunks: List[str] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        piece = text[start:end]
        if end < text_len:
            tail = piece[max(0, len(piece) - 120):]
            rel = max(tail.rfind(". "), tail.rfind("? "), tail.rfind("! "))
            if rel != -1:
                end = start + (len(piece) - len(tail) + rel + 1)
                piece = text[start:end]
        chunks.append(piece.strip())
        if end >= text_len:
            break
        start = max(0, end - chunk_overlap)
    return [c for c in chunks if c]
