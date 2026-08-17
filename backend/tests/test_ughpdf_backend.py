"""Ugh!PDF backend regression tests.
Covers: health, tools registry, auth (signup/login/me/duplicate/google),
server-side PDF tools, AI tools (Emergent LLM), credit consumption,
file size limit, generic fallback, BYOK, billing mock unlock/checkout.
"""
import io
import os
import time
import uuid
import pytest
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
assert BASE_URL, "REACT_APP_BACKEND_URL missing"
API = f"{BASE_URL}/api"


# -------- helpers --------
def make_pdf(text="Hello world. This is a test invoice. Total: $42.00. Email: john@example.com. SSN: 123-45-6789.") -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.drawString(72, 720, text)
    c.drawString(72, 700, "Page 1 of the sample PDF for unit tests.")
    c.showPage()
    c.drawString(72, 720, "Page 2 content: 2+2=?, solve x+3=7.")
    c.showPage()
    c.save()
    return buf.getvalue()


def make_math_pdf() -> bytes:
    return make_pdf("Solve: 2x + 3 = 11. What is x? Also: 5 * 6 = ?")


@pytest.fixture(scope="session")
def sample_pdf():
    return make_pdf()


@pytest.fixture(scope="session")
def fresh_user():
    """Create a brand new user for the run."""
    email = f"test_{uuid.uuid4().hex[:8]}@ughpdf.com"
    pw = "testpass123"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": pw, "name": "T"})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"email": email, "password": pw, "token": data["token"], "user": data["user"]}


@pytest.fixture(scope="session")
def auth_headers(fresh_user):
    return {"Authorization": f"Bearer {fresh_user['token']}"}


@pytest.fixture(scope="session")
def lifetime_user():
    """A separate user upgraded to lifetime for AI-heavy tests."""
    email = f"life_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123", "name": "L"})
    assert r.status_code == 200
    token = r.json()["token"]
    r2 = requests.post(f"{API}/billing/mock-unlock", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200, r2.text
    # Verify by fetching /auth/me
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["plan"] == "lifetime"
    return {"email": email, "token": token, "user": me}


@pytest.fixture(scope="session")
def life_headers(lifetime_user):
    return {"Authorization": f"Bearer {lifetime_user['token']}"}


# ================= HEALTH & REGISTRY =================
def test_health_root():
    r = requests.get(f"{API}/")
    assert r.status_code == 200
    d = r.json()
    assert d["app"] == "Ugh!PDF"
    assert d["tools"] >= 52  # spec says 52-53


def test_tools_list():
    r = requests.get(f"{API}/tools")
    assert r.status_code == 200
    d = r.json()
    assert len(d["categories"]) == 6
    assert len(d["tools"]) >= 52
    ids = {t["id"] for t in d["tools"]}
    for must in ("merge", "ai-chat", "protect", "unlock", "bates"):
        assert must in ids


@pytest.mark.parametrize("tid", ["merge", "ai-chat", "protect", "pdf-to-text"])
def test_tool_by_id(tid):
    r = requests.get(f"{API}/tools/{tid}")
    assert r.status_code == 200
    assert r.json()["id"] == tid


def test_tool_by_id_404():
    r = requests.get(f"{API}/tools/no-such-tool-xyz")
    assert r.status_code == 404


# ================= AUTH =================
def test_signup_new(fresh_user):
    u = fresh_user["user"]
    assert u["plan"] == "free"
    assert u["ai_credits"] == 5
    assert u["email"] == fresh_user["email"]


def test_signup_duplicate(fresh_user):
    r = requests.post(f"{API}/auth/signup",
                      json={"email": fresh_user["email"], "password": "abcdef", "name": "x"})
    assert r.status_code == 400


def test_login_valid(fresh_user):
    r = requests.post(f"{API}/auth/login",
                      json={"email": fresh_user["email"], "password": fresh_user["password"]})
    assert r.status_code == 200
    assert "token" in r.json() and "user" in r.json()


def test_login_invalid(fresh_user):
    r = requests.post(f"{API}/auth/login",
                      json={"email": fresh_user["email"], "password": "wrong-pass"})
    assert r.status_code == 401


def test_me_authed(auth_headers, fresh_user):
    r = requests.get(f"{API}/auth/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["email"] == fresh_user["email"]


def test_me_no_token():
    r = requests.get(f"{API}/auth/me")
    assert r.status_code == 401


def test_google_invalid_session():
    r = requests.post(f"{API}/auth/google", json={"session_id": "not-a-real-session-xxx"})
    assert r.status_code == 401


# ================= SERVER PDF TOOLS =================
def test_protect(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/protect/run", headers=life_headers,
                      files=files, data={"password": "sekret123"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    # Save for unlock test
    test_protect.protected_pdf = r.content


def test_unlock(life_headers):
    prot = getattr(test_protect, "protected_pdf", None)
    assert prot, "protect must run first"
    files = {"file": ("p.pdf", prot, "application/pdf")}
    r = requests.post(f"{API}/tools/unlock/run", headers=life_headers,
                      files=files, data={"password": "sekret123"})
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"


def test_pdf_to_text(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-to-text/run", headers=life_headers, files=files)
    assert r.status_code == 200, r.text
    assert "text/plain" in r.headers.get("content-type", "")
    assert b"invoice" in r.content.lower() or b"page" in r.content.lower()


def test_pdf_to_markdown(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-to-markdown/run", headers=life_headers, files=files)
    assert r.status_code == 200
    assert r.content.startswith(b"# ")


def test_bates(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/bates/run", headers=life_headers,
                      files=files, data={"prefix": "TEST", "start": 1})
    assert r.status_code == 200, r.text
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


def test_generic_word_to_pdf(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/word-to-pdf/run-generic", headers=life_headers, files=files)
    assert r.status_code == 200


# ================= AI TOOLS =================
def test_ai_summarize(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/ai-summarize/run", headers=life_headers, files=files, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "summary" in d and isinstance(d["summary"], str) and len(d["summary"]) > 5


def test_ai_chat(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/ai-chat/run", headers=life_headers,
                      files=files, data={"question": "What is the total?"}, timeout=120)
    assert r.status_code == 200, r.text
    assert "answer" in r.json()


def test_ai_extract(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/ai-extract/run", headers=life_headers,
                      files=files, data={"hint": "invoice"}, timeout=120)
    assert r.status_code == 200, r.text
    assert "data" in r.json()


def test_ai_redact(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/ai-redact/run", headers=life_headers, files=files, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "findings" in d and "count" in d


def test_ai_math(life_headers):
    pdf = make_math_pdf()
    files = {"file": ("m.pdf", pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/ai-math/run", headers=life_headers, files=files, timeout=120)
    assert r.status_code == 200, r.text
    assert "solution" in r.json()


def test_ai_ocr(life_headers, sample_pdf):
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r = requests.post(f"{API}/tools/ai-ocr/run", headers=life_headers, files=files, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "text_by_page" in d and "scanned_pages" in d and "message" in d


def test_ai_visual_diff(life_headers, sample_pdf):
    pdf2 = make_pdf("Different content: Total: $99.00. Bob@example.com.")
    files = [("file_a", ("a.pdf", sample_pdf, "application/pdf")),
             ("file_b", ("b.pdf", pdf2, "application/pdf"))]
    r = requests.post(f"{API}/tools/ai-visual-diff/run", headers=life_headers, files=files, timeout=120)
    assert r.status_code == 200, r.text
    assert "diff" in r.json()


# ================= CREDITS / LIMITS =================
def test_credit_consumption_and_out_of_credits(sample_pdf):
    # Fresh free user has 5 credits. ai-extract costs 3, ai-summarize 2 -> total 5 used.
    email = f"cred_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123"})
    assert r.status_code == 200
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    files = {"file": ("s.pdf", sample_pdf, "application/pdf")}

    # 1st: summarize costs 2 -> credits 5->3
    r1 = requests.post(f"{API}/tools/ai-summarize/run", headers=h, files=files, timeout=120)
    assert r1.status_code == 200
    me = requests.get(f"{API}/auth/me", headers=h).json()
    assert me["ai_credits"] == 3
    assert me["ops_today"] >= 1

    # 2nd: extract costs 3 -> credits 3->0
    files2 = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r2 = requests.post(f"{API}/tools/ai-extract/run", headers=h, files=files2,
                       data={"hint": ""}, timeout=120)
    assert r2.status_code == 200
    me2 = requests.get(f"{API}/auth/me", headers=h).json()
    assert me2["ai_credits"] == 0

    # 3rd: any AI call -> 402
    files3 = {"file": ("s.pdf", sample_pdf, "application/pdf")}
    r3 = requests.post(f"{API}/tools/ai-chat/run", headers=h, files=files3,
                       data={"question": "hi"}, timeout=60)
    assert r3.status_code == 402, r3.text


def test_file_size_limit_free(sample_pdf):
    email = f"big_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123"})
    tok = r.json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    # Make a >25MB blob
    big = b"%PDF-1.4\n" + b"0" * (26 * 1024 * 1024)
    files = {"file": ("big.pdf", big, "application/pdf")}
    r = requests.post(f"{API}/tools/pdf-to-text/run", headers=h, files=files)
    assert r.status_code == 413, r.status_code


# ================= BYOK =================
def test_byok(auth_headers):
    r = requests.post(f"{API}/auth/byok", headers=auth_headers,
                      json={"openai_key": "sk-test-abc", "gemini_key": "gem-xyz"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["byok_openai"] is True
    assert d["byok_gemini"] is True


# ================= BILLING =================
def test_billing_mock_unlock():
    email = f"pay_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "testpass123"})
    tok = r.json()["token"]
    r2 = requests.post(f"{API}/billing/mock-unlock", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 200, r2.text
    assert r2.json().get("plan") == "lifetime"
    # Verify persistence via /auth/me
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["plan"] == "lifetime"
    assert me["ai_credits"] == 50


def test_billing_geo():
    r = requests.get(f"{API}/billing/geo")
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("country", "currency", "symbol", "amount", "display"):
        assert k in d, f"missing key {k}"
    # In container network, country resolves via ipapi.co; expect US w/ USD $1
    # (tolerate other countries as fallback if geo detection returns something else)
    assert d["amount"] == 1.0
    assert d["display"].endswith("1")
    assert d["currency"] in ("USD", "CAD", "GBP", "EUR", "AUD", "NZD", "INR")


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
    assert "url" in d
    assert d["url"].startswith("https://checkout.stripe.com"), f"Expected real Stripe URL, got: {d['url']}"
    assert "session_id" in d and d["session_id"].startswith("cs_")
    assert d["amount"] == 1.0
    assert d["currency"] in ("USD", "CAD", "GBP", "EUR", "AUD", "NZD", "INR")
    # Stash for status test
    test_billing_checkout_real_stripe.session_id = d["session_id"]
    test_billing_checkout_real_stripe.currency = d["currency"]


def test_payments_status_created():
    sid = getattr(test_billing_checkout_real_stripe, "session_id", None)
    assert sid, "checkout must run first"
    r = requests.get(f"{API}/payments/status/{sid}")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["session_id"] == sid
    # Status is initiated until payment completes
    assert d["status"] in ("initiated", "completed")
    assert d["payment_status"] in ("pending", "paid")
    assert d["amount"] == 1.0


def test_payments_status_unknown_404():
    r = requests.get(f"{API}/payments/status/cs_test_does_not_exist_xyz")
    assert r.status_code == 404


def test_stripe_webhook_invalid_signature():
    # No valid stripe-signature header -> 400
    r = requests.post(f"{API}/webhook/stripe", data=b'{"type":"noop"}',
                      headers={"stripe-signature": "t=1,v1=fake"})
    assert r.status_code == 400
