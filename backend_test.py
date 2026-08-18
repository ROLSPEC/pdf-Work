"""
Ugh!PDF Backend Test Suite
Tests all backend endpoints for the restored app from GitHub.
"""
import io
import os
import uuid
import time
import requests
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER

# Get backend URL from frontend/.env
BASE_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
            break

assert BASE_URL, "REACT_APP_BACKEND_URL not found in frontend/.env"
API = f"{BASE_URL}/api"

print(f"Testing backend at: {API}")

# Test credentials
TEST_EMAIL = f"alice.johnson_{uuid.uuid4().hex[:8]}@ughpdf.com"
TEST_PASSWORD = "SecurePass2024!"
TEST_TOKEN = None
TEST_USER = None

def make_sample_pdf(text="Sample PDF for testing Ugh!PDF tools."):
    """Generate a small valid PDF for testing."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    c.drawString(72, 720, text)
    c.drawString(72, 700, "This is a test document for PDF operations.")
    c.showPage()
    c.drawString(72, 720, "Page 2: Additional content for testing.")
    c.showPage()
    c.save()
    return buf.getvalue()

def make_multipage_pdf():
    """Generate a multi-page PDF for semantic search testing."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    
    # Page 1: Company leadership
    c.drawString(72, 720, "Executive Team Overview")
    c.drawString(72, 700, "Our CEO Jennifer Martinez leads the executive team and sets")
    c.drawString(72, 680, "company vision and strategic direction for the organization.")
    c.showPage()
    
    # Page 2: Product roadmap
    c.drawString(72, 720, "Product Development Roadmap")
    c.drawString(72, 700, "The 2026 Roadmap outlines upcoming product features,")
    c.drawString(72, 680, "platform milestones, and technical improvements planned.")
    c.showPage()
    
    # Page 3: Financial information
    c.drawString(72, 720, "Financial Performance Report")
    c.drawString(72, 700, "Financial margins, profits, and revenue growth for the")
    c.drawString(72, 680, "fiscal year exceeded expectations with strong performance.")
    c.showPage()
    
    c.save()
    return buf.getvalue()

# ============ Test Results Tracking ============
test_results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def log_pass(test_name):
    test_results["passed"].append(test_name)
    print(f"✅ PASS: {test_name}")

def log_fail(test_name, error):
    test_results["failed"].append(f"{test_name}: {error}")
    print(f"❌ FAIL: {test_name}")
    print(f"   Error: {error}")

def log_warning(test_name, warning):
    test_results["warnings"].append(f"{test_name}: {warning}")
    print(f"⚠️  WARNING: {test_name}")
    print(f"   Warning: {warning}")

# ============ AUTH TESTS ============
def test_health():
    """Test backend health endpoint."""
    try:
        r = requests.get(f"{API}/", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data["app"] == "Ugh!PDF", f"Expected app='Ugh!PDF', got {data.get('app')}"
        assert data["tools"] == 46, f"Expected 46 tools, got {data.get('tools')}"
        assert data["categories"] == 6, f"Expected 6 categories, got {data.get('categories')}"
        log_pass("Backend health check")
    except Exception as e:
        log_fail("Backend health check", str(e))

def test_signup():
    """Test user signup and save credentials."""
    global TEST_TOKEN, TEST_USER
    try:
        r = requests.post(f"{API}/auth/signup", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "name": "Alice Johnson"
        }, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        TEST_TOKEN = data["token"]
        TEST_USER = data["user"]
        
        # Save credentials
        with open("/app/memory/test_credentials.md", "w") as f:
            f.write("# Ugh!PDF Test Credentials\n\n")
            f.write(f"**Email:** {TEST_EMAIL}\n")
            f.write(f"**Password:** {TEST_PASSWORD}\n")
            f.write(f"**Token:** {TEST_TOKEN}\n")
            f.write(f"**User ID:** {TEST_USER['id']}\n")
            f.write(f"**Plan:** {TEST_USER['plan']}\n")
        
        log_pass("User signup (credentials saved to /app/memory/test_credentials.md)")
    except Exception as e:
        log_fail("User signup", str(e))

def test_login():
    """Test user login."""
    try:
        r = requests.post(f"{API}/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "token" in data, "No token in response"
        assert "user" in data, "No user in response"
        log_pass("User login")
    except Exception as e:
        log_fail("User login", str(e))

def test_me():
    """Test /auth/me endpoint."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        r = requests.get(f"{API}/auth/me", headers=headers, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["email"] == TEST_EMAIL, f"Email mismatch"
        assert data["plan"] == "free", f"Expected free plan, got {data.get('plan')}"
        log_pass("GET /auth/me")
    except Exception as e:
        log_fail("GET /auth/me", str(e))

def test_google_auth_invalid():
    """Test Google auth with invalid session_id (should fail gracefully)."""
    try:
        r = requests.post(f"{API}/auth/google", json={
            "session_id": "invalid-session-id-12345"
        }, timeout=10)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"
        log_pass("Google auth invalid session (graceful failure)")
    except Exception as e:
        log_fail("Google auth invalid session", str(e))

# ============ TOOLS REGISTRY TESTS ============
def test_tools_list():
    """Test GET /tools endpoint."""
    try:
        r = requests.get(f"{API}/tools", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert "tools" in data, "No tools in response"
        assert "categories" in data, "No categories in response"
        assert len(data["tools"]) == 46, f"Expected 46 tools, got {len(data['tools'])}"
        assert len(data["categories"]) == 6, f"Expected 6 categories, got {len(data['categories'])}"
        log_pass("GET /tools (46 tools, 6 categories)")
    except Exception as e:
        log_fail("GET /tools", str(e))

def test_tool_by_id_valid():
    """Test GET /tools/{tool_id} with valid ID."""
    try:
        r = requests.get(f"{API}/tools/protect", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        data = r.json()
        assert data["id"] == "protect", f"Expected id='protect', got {data.get('id')}"
        log_pass("GET /tools/protect (valid tool)")
    except Exception as e:
        log_fail("GET /tools/protect", str(e))

def test_tool_by_id_invalid():
    """Test GET /tools/{tool_id} with invalid ID."""
    try:
        r = requests.get(f"{API}/tools/nonexistent-tool-xyz", timeout=10)
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"
        log_pass("GET /tools/invalid-id (404 as expected)")
    except Exception as e:
        log_fail("GET /tools/invalid-id", str(e))

# ============ SERVER PDF TOOLS TESTS ============
def test_protect():
    """Test POST /tools/protect/run."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        pdf = make_sample_pdf("Testing password protection feature.")
        files = {"file": ("test.pdf", pdf, "application/pdf")}
        data = {"password": "MySecurePass123"}
        r = requests.post(f"{API}/tools/protect/run", headers=headers, files=files, data=data, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.content[:4] == b"%PDF", "Response is not a PDF"
        log_pass("POST /tools/protect/run")
        return r.content  # Return protected PDF for unlock test
    except Exception as e:
        log_fail("POST /tools/protect/run", str(e))
        return None

def test_unlock(protected_pdf):
    """Test POST /tools/unlock/run."""
    if not protected_pdf:
        log_warning("POST /tools/unlock/run", "Skipped (no protected PDF from previous test)")
        return
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        files = {"file": ("protected.pdf", protected_pdf, "application/pdf")}
        data = {"password": "MySecurePass123"}
        r = requests.post(f"{API}/tools/unlock/run", headers=headers, files=files, data=data, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.content[:4] == b"%PDF", "Response is not a PDF"
        log_pass("POST /tools/unlock/run")
    except Exception as e:
        log_fail("POST /tools/unlock/run", str(e))

def test_flatten():
    """Test POST /tools/flatten/run."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        pdf = make_sample_pdf("Testing flatten feature.")
        files = {"file": ("test.pdf", pdf, "application/pdf")}
        r = requests.post(f"{API}/tools/flatten/run", headers=headers, files=files, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.content[:4] == b"%PDF", "Response is not a PDF"
        log_pass("POST /tools/flatten/run")
    except Exception as e:
        log_fail("POST /tools/flatten/run", str(e))

def test_repair():
    """Test POST /tools/repair/run."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        pdf = make_sample_pdf("Testing repair feature.")
        files = {"file": ("test.pdf", pdf, "application/pdf")}
        r = requests.post(f"{API}/tools/repair/run", headers=headers, files=files, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.content[:4] == b"%PDF", "Response is not a PDF"
        log_pass("POST /tools/repair/run")
    except Exception as e:
        log_fail("POST /tools/repair/run", str(e))

def test_pdf_to_text():
    """Test POST /tools/pdf-to-text/run."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        pdf = make_sample_pdf("Testing PDF to text conversion.")
        files = {"file": ("test.pdf", pdf, "application/pdf")}
        r = requests.post(f"{API}/tools/pdf-to-text/run", headers=headers, files=files, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert "text/plain" in r.headers.get("content-type", ""), "Response is not text/plain"
        log_pass("POST /tools/pdf-to-text/run")
    except Exception as e:
        log_fail("POST /tools/pdf-to-text/run", str(e))

def test_pdf_to_markdown():
    """Test POST /tools/pdf-to-markdown/run."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        pdf = make_sample_pdf("Testing PDF to markdown conversion.")
        files = {"file": ("test.pdf", pdf, "application/pdf")}
        r = requests.post(f"{API}/tools/pdf-to-markdown/run", headers=headers, files=files, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.content.startswith(b"# "), "Response doesn't start with markdown header"
        log_pass("POST /tools/pdf-to-markdown/run")
    except Exception as e:
        log_fail("POST /tools/pdf-to-markdown/run", str(e))

def test_bates():
    """Test POST /tools/bates/run."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        pdf = make_sample_pdf("Testing Bates numbering feature.")
        files = {"file": ("test.pdf", pdf, "application/pdf")}
        data = {"prefix": "LEGAL", "start": 1001}
        r = requests.post(f"{API}/tools/bates/run", headers=headers, files=files, data=data, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.content[:4] == b"%PDF", "Response is not a PDF"
        log_pass("POST /tools/bates/run")
    except Exception as e:
        log_fail("POST /tools/bates/run", str(e))

def test_exif_strip():
    """Test POST /tools/exif-strip-server/run."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        pdf = make_sample_pdf("Testing metadata stripping feature.")
        files = {"file": ("test.pdf", pdf, "application/pdf")}
        r = requests.post(f"{API}/tools/exif-strip-server/run", headers=headers, files=files, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert r.content[:4] == b"%PDF", "Response is not a PDF"
        log_pass("POST /tools/exif-strip-server/run")
    except Exception as e:
        log_fail("POST /tools/exif-strip-server/run", str(e))

def test_generic_run():
    """Test POST /tools/{tool_id}/run-generic."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        pdf = make_sample_pdf("Testing generic tool runner.")
        files = {"file": ("test.pdf", pdf, "application/pdf")}
        r = requests.post(f"{API}/tools/pdf-to-html/run-generic", headers=headers, files=files, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        assert b"<html>" in r.content or b"<pre>" in r.content, "Response doesn't contain HTML"
        log_pass("POST /tools/pdf-to-html/run-generic")
    except Exception as e:
        log_fail("POST /tools/pdf-to-html/run-generic", str(e))

# ============ RAG TESTS ============
def test_pdf_search():
    """Test POST /tools/pdf-search/run (semantic search with fastembed)."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        pdf = make_multipage_pdf()
        files = {"file": ("search_test.pdf", pdf, "application/pdf")}
        data = {"query": "company leadership", "k": 5}
        
        print("   Note: First RAG call downloads fastembed model (BAAI/bge-small-en-v1.5), may take 60-120s...")
        r = requests.post(f"{API}/tools/pdf-search/run", headers=headers, files=files, data=data, timeout=180)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        
        result = r.json()
        assert "query" in result, "No query in response"
        assert "results" in result, "No results in response"
        assert "embedding_model" in result, "No embedding_model in response"
        assert "bge-small-en-v1.5" in result["embedding_model"], f"Wrong model: {result.get('embedding_model')}"
        assert len(result["results"]) > 0, "No search results returned"
        
        # Verify result structure
        for res in result["results"]:
            assert "page" in res, "Result missing page number"
            assert "score" in res, "Result missing score"
            assert "text" in res, "Result missing text"
            assert isinstance(res["score"], (int, float)), "Score is not numeric"
        
        log_pass("POST /tools/pdf-search/run (RAG semantic search)")
    except Exception as e:
        log_fail("POST /tools/pdf-search/run", str(e))

# ============ USER JOBS TESTS ============
def test_user_jobs_list():
    """Test GET /user/jobs."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        r = requests.get(f"{API}/user/jobs", headers=headers, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "jobs" in data, "No jobs in response"
        assert "ttl_hours" in data, "No ttl_hours in response"
        assert data["ttl_hours"] == 24, f"Expected ttl_hours=24, got {data.get('ttl_hours')}"
        log_pass("GET /user/jobs")
        return data["jobs"]
    except Exception as e:
        log_fail("GET /user/jobs", str(e))
        return []

def test_delete_job(jobs):
    """Test DELETE /user/jobs/{job_id}."""
    if not jobs:
        log_warning("DELETE /user/jobs/{job_id}", "Skipped (no jobs to delete)")
        return
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        job_id = jobs[0]["id"]
        r = requests.delete(f"{API}/user/jobs/{job_id}", headers=headers, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("deleted") == True, "Job not deleted"
        log_pass("DELETE /user/jobs/{job_id}")
    except Exception as e:
        log_fail("DELETE /user/jobs/{job_id}", str(e))

def test_delete_all_jobs():
    """Test DELETE /user/jobs."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        r = requests.delete(f"{API}/user/jobs", headers=headers, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "deleted" in data, "No deleted count in response"
        log_pass("DELETE /user/jobs (delete all)")
    except Exception as e:
        log_fail("DELETE /user/jobs", str(e))

# ============ BILLING TESTS ============
def test_billing_methods():
    """Test GET /billing/methods."""
    try:
        r = requests.get(f"{API}/billing/methods", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "gateways" in data, "No gateways in response"
        assert "recommended" in data, "No recommended gateway in response"
        
        gateways = {g["id"]: g for g in data["gateways"]}
        assert "stripe" in gateways, "Stripe gateway missing"
        assert "razorpay" in gateways, "Razorpay gateway missing"
        assert "paypal" in gateways, "PayPal gateway missing"
        
        # Check availability
        stripe_available = gateways["stripe"]["available"]
        razorpay_available = gateways["razorpay"]["available"]
        paypal_available = gateways["paypal"]["available"]
        
        log_pass(f"GET /billing/methods (Stripe: {stripe_available}, Razorpay: {razorpay_available}, PayPal: {paypal_available})")
    except Exception as e:
        log_fail("GET /billing/methods", str(e))

def test_billing_mock_unlock():
    """Test POST /billing/mock-unlock (upgrade to lifetime)."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        r = requests.post(f"{API}/billing/mock-unlock", headers=headers, timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("plan") == "lifetime", f"Expected plan='lifetime', got {data.get('plan')}"
        log_pass("POST /billing/mock-unlock (upgraded to lifetime)")
    except Exception as e:
        log_fail("POST /billing/mock-unlock", str(e))

def test_billing_double_buy_guard():
    """Test that lifetime users get 409 on checkout endpoints."""
    try:
        headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
        
        # Test Stripe checkout
        r = requests.post(f"{API}/billing/checkout", headers=headers, 
                         json={"origin_url": BASE_URL}, timeout=10)
        assert r.status_code == 409, f"Expected 409 for Stripe checkout, got {r.status_code}"
        assert "lifetime" in r.text.lower() or "already" in r.text.lower(), "Wrong error message"
        
        # Test Razorpay order
        r = requests.post(f"{API}/billing/razorpay/order", headers=headers,
                         json={"amount": 100, "currency": "INR"}, timeout=10)
        assert r.status_code == 409, f"Expected 409 for Razorpay order, got {r.status_code}"
        
        # Test PayPal order (should be 503 unconfigured, not 409, but let's check)
        r = requests.post(f"{API}/billing/paypal/order", headers=headers,
                         json={"amount": 1.0, "currency": "USD"}, timeout=10)
        # PayPal is unconfigured, so expect 503 OR 409
        assert r.status_code in (409, 503), f"Expected 409 or 503 for PayPal order, got {r.status_code}"
        
        log_pass("Billing double-buy guard (409 for lifetime users)")
    except Exception as e:
        log_fail("Billing double-buy guard", str(e))

# ============ MAIN TEST RUNNER ============
def run_all_tests():
    """Run all backend tests in order."""
    print("\n" + "="*70)
    print("UGHPDF BACKEND TEST SUITE")
    print("="*70 + "\n")
    
    # Health check
    test_health()
    
    # Auth tests
    test_signup()
    if not TEST_TOKEN:
        print("\n❌ Cannot continue without valid token. Stopping tests.")
        return
    
    test_login()
    test_me()
    test_google_auth_invalid()
    
    # Tools registry
    test_tools_list()
    test_tool_by_id_valid()
    test_tool_by_id_invalid()
    
    # Server PDF tools
    protected_pdf = test_protect()
    test_unlock(protected_pdf)
    test_flatten()
    test_repair()
    test_pdf_to_text()
    test_pdf_to_markdown()
    test_bates()
    test_exif_strip()
    test_generic_run()
    
    # RAG (semantic search)
    test_pdf_search()
    
    # User jobs
    jobs = test_user_jobs_list()
    test_delete_job(jobs)
    test_delete_all_jobs()
    
    # Billing
    test_billing_methods()
    test_billing_mock_unlock()
    test_billing_double_buy_guard()
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"✅ PASSED: {len(test_results['passed'])}")
    print(f"❌ FAILED: {len(test_results['failed'])}")
    print(f"⚠️  WARNINGS: {len(test_results['warnings'])}")
    
    if test_results["failed"]:
        print("\nFailed tests:")
        for fail in test_results["failed"]:
            print(f"  - {fail}")
    
    if test_results["warnings"]:
        print("\nWarnings:")
        for warn in test_results["warnings"]:
            print(f"  - {warn}")
    
    print("\n" + "="*70 + "\n")
    
    return len(test_results["failed"]) == 0

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
