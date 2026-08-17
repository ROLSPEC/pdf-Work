"""RAG (Retrieval-Augmented Generation) for Chat with PDF.

Pipeline:
1. Extract text per page from PDF (via pdf_ops).
2. Chunk text into ~400-word chunks with page attribution + overlap.
3. Vectorize chunks with TF-IDF (fast, no external API, no GPU needed).
4. Cache chunks + vectorizer per file SHA-256 hash in MongoDB → repeat uploads are free.
5. On query: vectorize question, cosine-similarity against chunks, return top-K.
6. Feed retrieved chunks (with page numbers) to LLM as grounding context.
7. LLM answers with [p.N] citations only from provided chunks.
"""

import hashlib
import pickle
import base64
import re
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import pdf_ops


CHUNK_WORDS = 400
CHUNK_OVERLAP = 50
TOP_K = 5


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p for p in parts if p]


def build_chunks(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build chunks preserving page attribution. Each chunk ~ CHUNK_WORDS words."""
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
                # overlap: keep last CHUNK_OVERLAP words
                cur_text = " ".join(cur).split()
                cur = cur_text[-CHUNK_OVERLAP:] if len(cur_text) > CHUNK_OVERLAP else []
                count = len(cur)
            cur.extend(words)
            count += len(words)
        if cur:
            chunks.append({"chunk_id": idx, "page": page_no, "text": " ".join(cur)})
            idx += 1
    return chunks


def _serialize_vectorizer(v: TfidfVectorizer, matrix) -> str:
    return base64.b64encode(pickle.dumps({"v": v, "m": matrix})).decode("ascii")


def _deserialize_vectorizer(b64: str):
    d = pickle.loads(base64.b64decode(b64.encode("ascii")))
    return d["v"], d["m"]


async def get_or_build_index(db, file_bytes: bytes) -> Tuple[str, List[Dict[str, Any]], TfidfVectorizer, Any]:
    """Return (file_hash, chunks, vectorizer, matrix). Uses cache when possible."""
    fh = file_hash(file_bytes)
    cached = await db.rag_indexes.find_one({"_id": fh})
    if cached:
        v, m = _deserialize_vectorizer(cached["blob"])
        return fh, cached["chunks"], v, m
    # Build fresh index
    pages = pdf_ops.extract_text_by_page(file_bytes)
    chunks = build_chunks(pages)
    if not chunks:
        # Fallback: create single-chunk from concatenated text
        text = "\n".join(p.get("text", "") for p in pages).strip() or "(empty)"
        chunks = [{"chunk_id": 0, "page": 1, "text": text}]
    corpus = [c["text"] for c in chunks]
    v = TfidfVectorizer(ngram_range=(1, 2), max_features=8000, stop_words="english", sublinear_tf=True)
    matrix = v.fit_transform(corpus)
    await db.rag_indexes.insert_one({
        "_id": fh,
        "chunks": chunks,
        "blob": _serialize_vectorizer(v, matrix),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_chunks": len(chunks),
    })
    return fh, chunks, v, matrix


def retrieve(v: TfidfVectorizer, matrix, chunks: List[Dict[str, Any]], question: str, k: int = TOP_K) -> List[Dict[str, Any]]:
    if not chunks:
        return []
    q_vec = v.transform([question])
    sims = cosine_similarity(q_vec, matrix).flatten()
    top_idx = sims.argsort()[::-1][:k]
    out = []
    for i in top_idx:
        if sims[i] <= 0:
            continue
        c = dict(chunks[int(i)])
        c["score"] = float(sims[int(i)])
        out.append(c)
    # If nothing scored > 0, still return top-k without score filter (fallback)
    if not out:
        for i in top_idx[:min(k, len(chunks))]:
            c = dict(chunks[int(i)])
            c["score"] = float(sims[int(i)])
            out.append(c)
    return out


def build_context(retrieved: List[Dict[str, Any]]) -> str:
    parts = []
    for r in retrieved:
        parts.append(f"[p.{r['page']}] {r['text']}")
    return "\n\n".join(parts)
