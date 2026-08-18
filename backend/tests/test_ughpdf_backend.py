"""Ugh!PDF backend regression tests — iter 6 (no AI, 24h ephemeral job history).

Covers:
- Health & tools registry (45 tools, 5 categories, no AI category)
- All legacy AI endpoints return 404
- Auth: signup/login/me/duplicate/google — user_public has NO ai_credits
- Server PDF tools: protect, unlock, flatten, repair, pdf-to-text, pdf-to-markdown, bates, generic pdf-to-html
- Job logging: /api/user/jobs list, delete-one, delete-all, cross-user isolation
- MongoDB TTL index on user_jobs.expires_at + (user_id, created_at desc) compound index
- Free plan enforcement: 25MB size limit (413), 10 daily ops (429)
- Billing: geo, real Stripe checkout, mock-unlock (no ai_credits)
"""
import io
import os
import uuid
import time
from datetime import datetime, timedelta, timezone
import pytest
import requests
import pymongo
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"


# -------- helpers --------
def make_pdf(text="Hello world. Invoice total: $42.00.") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.drawString(72, 720, text)
    c.showPage()
    c.drawString(72, 720, "Page 2 of the sample PDF.")
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_pdf():
    return make_pdf()


@pytest.fixture(scope="session")
def fresh_user():
    email = f"test_{uuid.uuid4().hex[:8]}@ughpdf.com"
    pw = "testpass123"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": pw, "name": "T"})
    assert r.status_code == 200, r.text
    d = r.json()
    return {"email": email, "password": pw, "token": d["token"], "user": d["user"]}


@pytest.fixture(scope="session")
def auth_headers(fresh_user):
    return {"Authorization": f"Bearer {fresh_user['token']}"}


@pytest.fixture(scope="session")
def lifetime_user():
    email = f"life_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123", "name": "L"})
    assert r.status_code == 200
    tok = r.json()["token"]
    r2 = requests.post(f"{API}/billing/mock-unlock", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 200, r2.text
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["plan"] == "lifetime"
    return {"email": email, "token": tok, "user": me}


@pytest.fixture(scope="session")
def life_headers(lifetime_user):
    return {"Authorization": f"Bearer {lifetime_user['token']}"}


# ================= HEALTH & REGISTRY =================
def test_health_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    d = r.json()
    assert d["app"] == "Ugh!PDF"
    assert d["tools"] == 46, f"expected 46 tools, got {d['tools']}"
    assert d["categories"] == 6


def test_tools_list_46_6_with_search():
    r = requests.get(f"{API}/tools")
    assert r.status_code == 200
    d = r.json()
    assert len(d["categories"]) == 6
    cat_ids = {c["id"] for c in d["categories"]}
    assert "ai" not in cat_ids
    assert cat_ids == {"convert", "organize", "optimize", "edit", "security", "search"}
    assert len(d["tools"]) == 46
    ids = {t["id"] for t in d["tools"]}
    # No AI tool id must appear
    ai_leaks = [i for i in ids if i.startswith("ai-")]
    assert ai_leaks == [], f"AI tool ids leaked: {ai_leaks}"
    # Core tools present
    for must in ("merge", "protect", "unlock", "bates", "pdf-to-text", "pdf-to-markdown", "pdf-search"):
        assert must in ids
    # pdf-search is in search category
    tools_by_id = {t["id"]: t for t in d["tools"]}
    assert tools_by_id["pdf-search"]["cat"] == "search"


def test_local_tools_registered():
    r = requests.get(f"{API}/tools")
    d = r.json()
    by_id = {t["id"]: t for t in d["tools"]}
    for lid in ("merge", "split", "rotate", "compress"):
        assert by_id[lid]["engine"] == "local"


@pytest.mark.parametrize("tid", ["merge", "protect", "pdf-to-text", "bates"])
def test_tool_by_id(tid):
    r = requests.get(f"{API}/tools/{tid}")
    assert r.status_code == 200
    assert r.json()["id"] == tid


def test_tool_by_id_404():
    r = requests.get(f"{API}/tools/no-such-tool-xyz")
    assert r.status_code == 404


# ================= AI REMOVAL (all must 404) =================
@pytest.mark.parametrize("ai_id", [
    "ai-chat", "ai-summarize", "ai-redact", "ai-extract",
    "ai-audiobook", "ai-math", "ai-ocr", "ai-visual-diff",
])
def test_ai_endpoints_removed(ai_id, life_headers, sample_pdf):
    """Legacy AI endpoints must not exist. Registry lookup returns 404 via generic route."""
    # /tools/{id} should 404
    r = requests.get(f"{API}/tools/{ai_id}")
    assert r.status_code == 404, f"{ai_id} still in tools registry"
    # POST /tools/{id}/run — no explicit route registered; FastAPI returns 404 or 405
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/{ai_id}/run", headers=life_headers, files=files)
    assert r.status_code in (404, 405), f"{ai_id}/run returned {r.status_code}"


# ================= AUTH =================
def test_signup_no_ai_credits(fresh_user):
    u = fresh_user["user"]
    assert u["plan"] == "free"
    assert "ai_credits" not in u
    assert "ai_credits_reset_at" not in u
    # New shape
    for k in ("id", "email", "name", "plan", "ops_today", "ops_reset_at", "max_file_mb", "daily_ops_limit"):
        assert k in u, f"missing {k}"
    assert u["max_file_mb"] == 25
    assert u["daily_ops_limit"] == 10


def test_signup_duplicate(fresh_user):
    r = requests.post(f"{API}/auth/signup", json={"email": fresh_user["email"], "password": "abcdef"})
    assert r.status_code == 400


def test_login_valid(fresh_user):
    r = requests.post(f"{API}/auth/login", json={"email": fresh_user["email"], "password": fresh_user["password"]})
    assert r.status_code == 200
    assert "token" in r.json() and "user" in r.json()
    assert "ai_credits" not in r.json()["user"]


def test_login_invalid(fresh_user):
    r = requests.post(f"{API}/auth/login", json={"email": fresh_user["email"], "password": "wrong"})
    assert r.status_code == 401


def test_me_authed(auth_headers, fresh_user):
    r = requests.get(f"{API}/auth/me", headers=auth_headers)
    assert r.status_code == 200
    d = r.json()
    assert d["email"] == fresh_user["email"]
    assert "ai_credits" not in d


def test_me_no_token():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code == 401


def test_google_invalid_session():
    r = requests.post(f"{API}/auth/google", json={"session_id": "not-a-real-session-xxx"})
    assert r.status_code == 401


# ================= SERVER PDF TOOLS + JOB LOGGING =================
def test_protect(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/protect/run", headers=life_headers,
                      files=files, data={"password": "sekret123"})
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
    test_protect.protected_pdf = r.content


def test_unlock(life_headers):
    prot = getattr(test_protect, "protected_pdf", None)
    assert prot
    files = {"file": ("p.pdf", prot, "application/pdf")}
    r = requests.post(f"{API}/tools/unlock/run", headers=life_headers,
                      files=files, data={"password": "sekret123"})
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"


def test_pdf_to_text(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-to-text/run", headers=life_headers, files=files)
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")


def test_pdf_to_markdown(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-to-markdown/run", headers=life_headers, files=files)
    assert r.status_code == 200
    assert r.content.startswith(b"# ")


def test_bates(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/bates/run", headers=life_headers,
                      files=files, data={"prefix": "TEST", "start": 1})
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_flatten(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/flatten/run", headers=life_headers, files=files)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_repair(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/repair/run", headers=life_headers, files=files)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_generic_pdf_to_html(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-to-html/run-generic", headers=life_headers, files=files)
    assert r.status_code == 200
    assert b"<html>" in r.content


# ================= JOBS (24h TTL) =================
def test_jobs_listed_after_protect(life_headers):
    """After the protect test above ran, GET /user/jobs should include a job at top."""
    r = requests.get(f"{API}/user/jobs", headers=life_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ttl_hours"] == 24
    assert isinstance(d["jobs"], list) and len(d["jobs"]) > 0
    # Find at least one 'protect' entry
    protect_jobs = [j for j in d["jobs"] if j["tool_id"] == "protect"]
    assert protect_jobs, "no protect job found in history"
    j = protect_jobs[0]
    for k in ("id", "tool_id", "tool_name", "filename", "size_bytes", "engine", "status", "created_at", "expires_at"):
        assert k in j, f"missing job field {k}"
    assert j["engine"] == "server"
    assert j["status"] == "completed"
    # expires_at ~ created_at + 24h
    created = datetime.fromisoformat(j["created_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(j["expires_at"].replace("Z", "+00:00"))
    diff = (expires - created).total_seconds()
    assert 23.5 * 3600 <= diff <= 24.5 * 3600, f"expires_at not ~24h from created_at: {diff}s"


def test_delete_single_job(life_headers, sample_pdf):
    # Create a fresh job to delete
    files = {"file": ("del.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/flatten/run", headers=life_headers, files=files)
    assert r.status_code == 200
    jobs = requests.get(f"{API}/user/jobs", headers=life_headers).json()["jobs"]
    target = jobs[0]  # newest
    jid = target["id"]
    # Delete
    r = requests.delete(f"{API}/user/jobs/{jid}", headers=life_headers)
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    # Verify gone
    jobs2 = requests.get(f"{API}/user/jobs", headers=life_headers).json()["jobs"]
    assert jid not in [j["id"] for j in jobs2]


def test_delete_nonexistent_job_404(life_headers):
    r = requests.delete(f"{API}/user/jobs/does-not-exist-{uuid.uuid4().hex}", headers=life_headers)
    assert r.status_code == 404


def test_delete_cross_user_isolation(life_headers, sample_pdf):
    # user A creates a job
    files = {"file": ("iso.pdf", sample_pdf, "application/pdf")}
    requests.post(f"{API}/tools/flatten/run", headers=life_headers, files=files)
    jobs = requests.get(f"{API}/user/jobs", headers=life_headers).json()["jobs"]
    a_job_id = jobs[0]["id"]

    # user B signs up
    email = f"iso_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123"})
    b_headers = {"Authorization": f"Bearer {r.json()['token']}"}

    # B cannot delete A's job
    r = requests.delete(f"{API}/user/jobs/{a_job_id}", headers=b_headers)
    assert r.status_code == 404, "user B should not be able to delete user A's job"

    # A's job still exists
    jobs_a = requests.get(f"{API}/user/jobs", headers=life_headers).json()["jobs"]
    assert a_job_id in [j["id"] for j in jobs_a]


def test_delete_all_jobs():
    # Fresh isolated user so we don't nuke lifetime_user's history mid-suite
    email = f"delall_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123"})
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    pdf = make_pdf()
    # create 3 jobs
    for _ in range(3):
        files = {"file": ("a.pdf", pdf, "application/pdf")}
        requests.post(f"{API}/tools/flatten/run", headers=h, files=files)
    jobs = requests.get(f"{API}/user/jobs", headers=h).json()["jobs"]
    assert len(jobs) == 3
    r = requests.delete(f"{API}/user/jobs", headers=h)
    assert r.status_code == 200
    assert r.json()["deleted"] == 3
    jobs2 = requests.get(f"{API}/user/jobs", headers=h).json()["jobs"]
    assert jobs2 == []


def test_mongo_ttl_index():
    """Verify user_jobs has a TTL index on expires_at (expireAfterSeconds=0)
    and a (user_id, created_at desc) compound index."""
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url:
        with open("/app/backend/.env") as f:
            for line in f:
                if line.startswith("MONGO_URL="):
                    mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("DB_NAME="):
                    db_name = line.split("=", 1)[1].strip().strip('"').strip("'")
    cli = pymongo.MongoClient(mongo_url)
    idx = list(cli[db_name].user_jobs.list_indexes())
    ttl = [i for i in idx if i.get("expireAfterSeconds") == 0 and "expires_at" in i["key"]]
    assert ttl, f"no TTL index on expires_at found: {idx}"
    compound = [i for i in idx if list(i["key"].items()) == [("user_id", 1), ("created_at", -1)]]
    assert compound, f"missing (user_id, created_at desc) compound index: {idx}"


# ================= FREE LIMITS =================
def test_file_size_limit_free(sample_pdf):
    email = f"big_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123"})
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    big = b"%PDF-1.4\n" + b"0" * (26 * 1024 * 1024)
    files = {"file": ("big.pdf", big, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-to-text/run", headers=h, files=files)
    assert r.status_code == 413


def test_daily_ops_limit_free(sample_pdf):
    email = f"lim_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123"})
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    # 10 daily ops for free plan → 11th must 429
    ok_count = 0
    for i in range(10):
        files = {"file": (f"a{i}.pdf", sample_pdf, "application/pdf")}
        r = requests.post(f"{API}/tools/pdf-to-text/run", headers=h, files=files)
        if r.status_code == 200:
            ok_count += 1
    assert ok_count == 10, f"expected 10 ok, got {ok_count}"
    files = {"file": ("over.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-to-text/run", headers=h, files=files)
    assert r.status_code == 429, f"expected 429 on 11th, got {r.status_code}"


# ================= BILLING =================
def test_billing_mock_unlock_no_ai_credits():
    email = f"pay_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123"})
    tok = r.json()["token"]
    r2 = requests.post(f"{API}/billing/mock-unlock", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 200, r2.text
    assert r2.json().get("plan") == "lifetime"
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["plan"] == "lifetime"
    assert "ai_credits" not in me
    assert me["max_file_mb"] == 100
    assert me["daily_ops_limit"] == 200


def test_billing_geo():
    r = requests.get(f"{API}/billing/geo")
    assert r.status_code == 200
    d = r.json()
    for k in ("country", "currency", "symbol", "amount", "display"):
        assert k in d
    assert d["amount"] == 1.0


def test_billing_checkout_real_stripe():
    email = f"co_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123"})
    tok = r.json()["token"]
    r2 = requests.post(
        f"{API}/billing/checkout",
        headers={"Authorization": f"Bearer {tok}"},
        json={"origin_url": "https://pdf-52-tools.preview.emergentagent.com"},
        timeout=30,
    )
    assert r2.status_code == 200, r2.text
    d = r2.json()
    assert d["url"].startswith("https://checkout.stripe.com"), d["url"]
    assert d["session_id"].startswith("cs_")


# ================= SEMANTIC SEARCH (pdf-search) =================
def _multipage_pdf(pages_texts):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    for t in pages_texts:
        # split by lines so long text is drawn
        y = 720
        for line in t.split("\n"):
            c.drawString(72, y, line[:110])
            y -= 14
        c.showPage()
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="session")
def semantic_pdf():
    return _multipage_pdf([
        "Our CEO Sarah Kim leads the executive team and sets company vision and strategy.",
        "The 2026 Roadmap outlines upcoming product features and platform milestones.",
        "Financial margins profits and revenue growth for the fiscal year were strong.",
    ])


def test_pdf_search_basic(life_headers, semantic_pdf):
    files = {"file": ("s.pdf", semantic_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-search/run", headers=life_headers,
                      files=files, data={"query": "credit card number", "k": 5}, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("query", "file_hash", "n_chunks_total", "n_results", "results", "embedding_model"):
        assert k in d
    assert "bge-small-en-v1.5" in d["embedding_model"]
    assert d["query"] == "credit card number"
    assert isinstance(d["results"], list) and len(d["results"]) >= 1
    for res in d["results"]:
        assert isinstance(res["page"], int)
        assert isinstance(res["score"], float)
        assert -1.1 <= res["score"] <= 1.1
        assert isinstance(res["text"], str) and len(res["text"]) > 0


def test_pdf_search_semantic_paraphrase(life_headers, semantic_pdf):
    """The whole point: paraphrased queries land on the right page."""
    files = {"file": ("s.pdf", semantic_pdf, "application/pdf")}
    # Query 'earnings' should rank page 3 (margins/profits)
    r = requests.post(f"{API}/tools/pdf-search/run", headers=life_headers,
                      files=files, data={"query": "earnings", "k": 3}, timeout=120)
    assert r.status_code == 200, r.text
    top_pages = [res["page"] for res in r.json()["results"]]
    assert 3 in top_pages[:2], f"expected page 3 in top results for 'earnings', got {top_pages}"

    # Query 'company leader' should rank page 1 (CEO Sarah Kim)
    files = {"file": ("s.pdf", semantic_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-search/run", headers=life_headers,
                      files=files, data={"query": "company leader", "k": 3}, timeout=120)
    assert r.status_code == 200
    top_pages = [res["page"] for res in r.json()["results"]]
    assert 1 in top_pages[:2], f"expected page 1 in top results for 'company leader', got {top_pages}"


def test_pdf_search_empty_query_400(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-search/run", headers=life_headers,
                      files=files, data={"query": "  ", "k": 3})
    assert r.status_code == 400


def test_pdf_search_k_clamps(life_headers, semantic_pdf):
    # k=1 -> exactly 1
    files = {"file": ("s.pdf", semantic_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-search/run", headers=life_headers,
                      files=files, data={"query": "revenue", "k": 1}, timeout=120)
    assert r.status_code == 200
    assert len(r.json()["results"]) == 1

    # k=99 -> clamped to <=20 (also <= n_chunks)
    files = {"file": ("s.pdf", semantic_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-search/run", headers=life_headers,
                      files=files, data={"query": "revenue", "k": 99}, timeout=120)
    assert r.status_code == 200
    d = r.json()
    assert len(d["results"]) <= 20
    assert len(d["results"]) <= d["n_chunks_total"]

    # k=0 -> clamped to 1
    files = {"file": ("s.pdf", semantic_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-search/run", headers=life_headers,
                      files=files, data={"query": "revenue", "k": 0}, timeout=120)
    assert r.status_code == 200
    assert len(r.json()["results"]) == 1


def test_pdf_search_cache_and_ttl_index(life_headers, semantic_pdf):
    """Same PDF twice should reuse cached index; verify Mongo doc + TTL index."""
    files = {"file": ("s.pdf", semantic_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-search/run", headers=life_headers,
                      files=files, data={"query": "first query", "k": 3}, timeout=120)
    assert r.status_code == 200
    fh1 = r.json()["file_hash"]

    t0 = time.time()
    files = {"file": ("s.pdf", semantic_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-search/run", headers=life_headers,
                      files=files, data={"query": "another different query", "k": 3}, timeout=60)
    dt = time.time() - t0
    assert r.status_code == 200
    fh2 = r.json()["file_hash"]
    assert fh1 == fh2

    # Verify Mongo doc & TTL index
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url:
        with open("/app/backend/.env") as f:
            for line in f:
                if line.startswith("MONGO_URL="):
                    mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("DB_NAME="):
                    db_name = line.split("=", 1)[1].strip().strip('"').strip("'")
    cli = pymongo.MongoClient(mongo_url)
    doc = cli[db_name].rag_indexes.find_one({"_id": fh1})
    assert doc is not None, "rag_indexes doc not cached"
    assert doc.get("version") == 3
    assert "bge-small-en-v1.5" in doc.get("model", "")
    assert doc.get("dim") == 384
    assert isinstance(doc.get("chunks"), list)
    assert isinstance(doc.get("vectors"), list)
    assert doc.get("expires_at") is not None
    # ~24h out
    created = doc.get("created_at")
    if created:
        diff = (doc["expires_at"] - created).total_seconds()
        assert 23 * 3600 <= diff <= 25 * 3600

    idx = list(cli[db_name].rag_indexes.list_indexes())
    ttl = [i for i in idx if i.get("expireAfterSeconds") == 0 and "expires_at" in i["key"]]
    assert ttl, f"no TTL index on rag_indexes.expires_at: {idx}"


def test_pdf_search_logs_job(life_headers, semantic_pdf):
    files = {"file": ("job.pdf", semantic_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-search/run", headers=life_headers,
                      files=files, data={"query": "revenue", "k": 2}, timeout=120)
    assert r.status_code == 200
    jobs = requests.get(f"{API}/user/jobs", headers=life_headers).json()["jobs"]
    assert any(j["tool_id"] == "pdf-search" for j in jobs), "pdf-search job not logged"


# ================= BILLING METHODS + RAZORPAY (unavailable) =================
def test_billing_methods_shape():
    r = requests.get(f"{API}/billing/methods")
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("country", "currency", "symbol", "display", "recommended", "gateways"):
        assert k in d, f"missing {k}"
    ids = {g["id"] for g in d["gateways"]}
    assert ids == {"stripe", "razorpay"}
    by_id = {g["id"]: g for g in d["gateways"]}
    assert by_id["stripe"]["available"] is True
    assert by_id["razorpay"]["available"] is False
    # Non-IN → recommended stripe
    if d["country"] != "IN":
        assert d["recommended"] == "stripe"


def test_razorpay_available_false():
    r = requests.get(f"{API}/billing/razorpay/available")
    assert r.status_code == 200
    d = r.json()
    assert d["available"] is False
    assert d.get("key_id", "") == ""


def test_razorpay_order_503_when_unconfigured(life_headers):
    r = requests.post(f"{API}/billing/razorpay/order",
                      headers=life_headers,
                      json={"amount": 100, "currency": "INR"})
    assert r.status_code == 503, r.text


def test_razorpay_verify_503_when_unconfigured(life_headers):
    r = requests.post(f"{API}/billing/razorpay/verify",
                      headers=life_headers,
                      json={"razorpay_order_id": "order_x", "razorpay_payment_id": "pay_x",
                            "razorpay_signature": "sig_x"})
    assert r.status_code == 503, r.text
