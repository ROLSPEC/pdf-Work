"""Semantic search over PDF chunks — NO LLM.

Users upload a PDF + query. We chunk the PDF by page, embed with fastembed
(BAAI/bge-small-en-v1.5, 384-dim), then return the top-K most similar chunks
with cosine-similarity scores and page numbers. No natural-language answers.
Cheap, private, no OpenAI/Google calls.

Cached indexes are stored in MongoDB `rag_indexes` and auto-expire after
FILE_TTL_HOURS (24h) via TTL index.
"""

import os
import hashlib
import re
import threading
import numpy as np
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta

import pdf_ops


CHUNK_WORDS = 400
CHUNK_OVERLAP = 50
TOP_K = 8
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
INDEX_VERSION = 3  # bump if the schema changes
FILE_TTL_HOURS = int(os.environ.get("FILE_TTL_HOURS", "24"))

_embedder = None
_lock = threading.Lock()


def get_embedder():
    """Lazy singleton — model file is downloaded once, cached on disk."""
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                from fastembed import TextEmbedding
                _embedder = TextEmbedding(model_name=EMBED_MODEL)
    return _embedder


def embed_texts(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    m = get_embedder()
    return np.array(list(m.embed(texts)), dtype=np.float32)


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    return [p for p in re.split(r"(?<=[.!?])\s+", text) if p]


def build_chunks(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Chunks that preserve page attribution. ~400 words with 50-word overlap."""
    chunks: List[Dict[str, Any]] = []
    idx = 0
    for page in pages:
        page_no = page["page"]
        text = (page.get("text") or "").strip()
        if not text:
            continue
        sentences = _split_sentences(text)
        cur, count = [], 0
        for s in sentences:
            words = s.split()
            if count + len(words) > CHUNK_WORDS and cur:
                chunks.append({"chunk_id": idx, "page": page_no, "text": " ".join(cur)})
                idx += 1
                cur_words = " ".join(cur).split()
                cur = cur_words[-CHUNK_OVERLAP:] if len(cur_words) > CHUNK_OVERLAP else []
                count = len(cur)
            cur.extend(words)
            count += len(words)
        if cur:
            chunks.append({"chunk_id": idx, "page": page_no, "text": " ".join(cur)})
            idx += 1
    return chunks


async def get_or_build_index(db, file_bytes: bytes) -> Tuple[str, List[Dict[str, Any]], np.ndarray]:
    fh = file_hash(file_bytes)
    cached = await db.rag_indexes.find_one({"_id": fh})
    if cached and cached.get("version") == INDEX_VERSION and "vectors" in cached:
        return fh, cached["chunks"], np.array(cached["vectors"], dtype=np.float32)

    pages = pdf_ops.extract_text_by_page(file_bytes)
    chunks = build_chunks(pages)
    if not chunks:
        text = "\n".join(p.get("text", "") for p in pages).strip() or "(empty)"
        chunks = [{"chunk_id": 0, "page": 1, "text": text}]

    import asyncio
    corpus = [c["text"] for c in chunks]
    matrix = await asyncio.to_thread(embed_texts, corpus)

    now = datetime.now(timezone.utc)
    doc = {
        "_id": fh,
        "version": INDEX_VERSION,
        "model": EMBED_MODEL,
        "chunks": chunks,
        "vectors": matrix.tolist(),
        "dim": int(matrix.shape[1]) if matrix.size else 384,
        "n_chunks": len(chunks),
        "created_at": now,
        "expires_at": now + timedelta(hours=FILE_TTL_HOURS),
    }
    await db.rag_indexes.replace_one({"_id": fh}, doc, upsert=True)
    return fh, chunks, matrix


def _normalize(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    n = np.where(n == 0, 1, n)
    return v / n


async def search(chunks: List[Dict[str, Any]], matrix: np.ndarray, query: str, k: int = TOP_K) -> List[Dict[str, Any]]:
    if not chunks or matrix.size == 0:
        return []
    import asyncio
    q_vec = await asyncio.to_thread(embed_texts, [query])
    if q_vec.size == 0:
        return []
    a = _normalize(q_vec)
    b = _normalize(matrix)
    sims = (a @ b.T).flatten()
    top_idx = sims.argsort()[::-1][:k]
    out = []
    for i in top_idx:
        c = dict(chunks[int(i)])
        c["score"] = float(sims[int(i)])
        out.append(c)
    return out
