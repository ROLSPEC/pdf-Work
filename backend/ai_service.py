"""AI service using Emergent LLM key via emergentintegrations."""
import os
import re
import json
from typing import AsyncGenerator, Optional
from emergentintegrations.llm.chat import LlmChat, UserMessage

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
CHAT_MODEL = os.environ.get("CHAT_MODEL", "gemini-2.5-flash")
EXTRACT_MODEL = os.environ.get("EXTRACT_MODEL", "gpt-4o-mini")


def _chat(system: str, model: str = CHAT_MODEL, provider: str = "gemini") -> LlmChat:
    session_id = f"ughpdf-{os.urandom(4).hex()}"
    return LlmChat(
        api_key=EMERGENT_KEY,
        session_id=session_id,
        system_message=system,
    ).with_model(provider, model)


async def chat_with_pdf(pdf_text: str, question: str) -> str:
    system = (
        "You are a helpful assistant that answers questions strictly from the provided PDF. "
        "Always cite page numbers like [p.3]. If unknown, say so."
    )
    llm = _chat(system, CHAT_MODEL, "gemini")
    context = pdf_text[:80000]
    msg = UserMessage(text=f"PDF CONTENT:\n{context}\n\nQUESTION: {question}")
    return await llm.send_message(msg)


async def chat_with_rag(context: str, question: str) -> str:
    """RAG-flavoured chat: `context` is a pre-retrieved set of top-K chunks
    (each prefixed with [p.N]). We instruct the LLM to answer ONLY from these
    chunks and cite pages inline.
    """
    system = (
        "You are a Retrieval-Augmented QA assistant. Answer the user's question "
        "using ONLY the provided PDF excerpts. Every claim must be followed by a "
        "citation like [p.3]. If the excerpts do not contain the answer, say "
        "'I couldn't find that in the document.' Do not invent facts."
    )
    llm = _chat(system, CHAT_MODEL, "gemini")
    msg = UserMessage(text=f"PDF EXCERPTS:\n{context}\n\nQUESTION: {question}\n\nAnswer with inline [p.N] citations.")
    return await llm.send_message(msg)


async def summarize(pdf_text: str) -> str:
    system = (
        "Summarize the PDF in a structured format: "
        "1) One-line TL;DR, 2) Key points as bullets, 3) Action items if any. "
        "Cite page numbers like [p.2] where relevant."
    )
    llm = _chat(system, CHAT_MODEL, "gemini")
    msg = UserMessage(text=pdf_text[:80000])
    return await llm.send_message(msg)


async def extract_structured(pdf_text: str, schema_hint: str = "") -> dict:
    system = (
        "Extract structured data as strict JSON. No commentary. "
        "If it's an invoice, return {invoice_number, date, vendor, line_items[], subtotal, tax, total}. "
        "If it's a resume, return {name, email, phone, skills[], experience[], education[]}. "
        "Otherwise return best-guess fields. Return ONLY a JSON object."
    )
    llm = _chat(system, EXTRACT_MODEL, "openai")
    hint = f"\nSchema hint: {schema_hint}" if schema_hint else ""
    msg = UserMessage(text=f"{pdf_text[:60000]}{hint}\n\nReturn JSON only.")
    resp = await llm.send_message(msg)
    m = re.search(r"\{[\s\S]*\}", resp)
    if not m:
        return {"raw": resp, "error": "no JSON found"}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"raw": resp, "error": "invalid JSON"}


PII_PATTERNS = {
    "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    "phone": re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ip": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}


def luhn_check(num: str) -> bool:
    digits = [int(c) for c in num if c.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def find_pii(text: str) -> list[dict]:
    found = []
    for kind, pat in PII_PATTERNS.items():
        for m in pat.finditer(text):
            val = m.group(0)
            if kind == "credit_card" and not luhn_check(val):
                continue
            found.append({"type": kind, "value": val, "position": m.start()})
    return found


async def ai_pii_verify(text: str) -> list[dict]:
    """LLM cross-check for name-like PII beyond regex."""
    regex_hits = find_pii(text)
    system = (
        "Identify any personal names, addresses, or identifiers in the text. "
        "Return JSON array: [{\"type\":\"name|address\",\"value\":\"...\"}]. "
        "Return ONLY a JSON array."
    )
    try:
        llm = _chat(system, EXTRACT_MODEL, "openai")
        resp = await llm.send_message(UserMessage(text=text[:20000]))
        m = re.search(r"\[[\s\S]*\]", resp)
        if m:
            llm_hits = json.loads(m.group(0))
            for h in llm_hits:
                if isinstance(h, dict) and "value" in h:
                    regex_hits.append({"type": h.get("type", "name"), "value": h["value"], "position": -1})
    except Exception:
        pass
    return regex_hits


async def solve_math(text: str) -> str:
    system = (
        "You are a math tutor. Solve every math problem in the PDF step-by-step. "
        "Show work clearly. Use plain text, no LaTeX. Cite page numbers."
    )
    llm = _chat(system, CHAT_MODEL, "gemini")
    return await llm.send_message(UserMessage(text=text[:60000]))


async def visual_diff(text_a: str, text_b: str) -> str:
    system = (
        "Compare two documents semantically. Return: "
        "1) Overall similarity 0-100, 2) Added content, 3) Removed content, 4) Changed sections. "
        "Be concise."
    )
    llm = _chat(system, CHAT_MODEL, "gemini")
    return await llm.send_message(UserMessage(text=f"DOC A:\n{text_a[:30000]}\n\nDOC B:\n{text_b[:30000]}"))
