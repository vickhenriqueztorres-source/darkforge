from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkDraft:
    chunk_index: int
    section_label: str
    chunk_text: str
    chunk_hash: str


def normalize_source_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def content_sha256(text: str) -> str:
    return hashlib.sha256(normalize_source_text(text).encode("utf-8")).hexdigest()


def split_semantic_chunks(text: str, max_chars: int = 600, overlap_chars: int = 80) -> list[ChunkDraft]:
    """Splits copies/scripts preserving hook/body/cta sections without breaking semantic units."""
    norm = normalize_source_text(text)
    if not norm:
        return []

    paragraphs = [p.strip() for p in norm.split("\n\n") if p.strip()]
    chunks: list[ChunkDraft] = []
    idx = 0
    total_paras = len(paragraphs)

    for p_idx, para in enumerate(paragraphs):
        label = "hook" if p_idx == 0 else ("cta" if p_idx == total_paras - 1 and total_paras > 2 else "body")
        lower = para.lower()
        if lower.startswith(("hook:", "[hook]")):
            label = "hook"
        elif lower.startswith(("cta:", "[cta]")):
            label = "cta"

        if len(para) <= max_chars:
            chunks.append(
                ChunkDraft(
                    chunk_index=idx,
                    section_label=label,
                    chunk_text=para,
                    chunk_hash=hashlib.sha256(para.encode("utf-8")).hexdigest(),
                )
            )
            idx += 1
        else:
            start = 0
            while start < len(para):
                end = min(len(para), start + max_chars)
                part = para[start:end].strip()
                if part:
                    chunks.append(
                        ChunkDraft(
                            chunk_index=idx,
                            section_label=label,
                            chunk_text=part,
                            chunk_hash=hashlib.sha256(part.encode("utf-8")).hexdigest(),
                        )
                    )
                    idx += 1
                if end >= len(para):
                    break
                start = max(start + 1, end - overlap_chars)
    return chunks
