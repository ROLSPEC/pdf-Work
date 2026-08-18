"""Double-buy prevention tests (iter 11).

Verifies that all 3 checkout endpoints return HTTP 409 for lifetime users
BEFORE any gateway availability / order-creation logic runs, and that fresh
free users still get real gateway responses (regression).
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

EXPECTED_MSG = "You're already on lifetime — no purchase needed 🎉"


# -------- fixtures --------
@pytest.fixture(scope="module")
def free_user():
    email = f"free_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup",
                      json={"email": email, "password": "testpass123", "name": "Free"})
    assert r.status_code == 200, r.text
    return {"email": email, "token": r.json()["token"]}


@pytest.fixture(scope="module")
def free_headers(free_user):
    return {"Authorization": f"Bearer {free_user['token']}"}


@pytest.fixture(scope="module")
def lifetime_user():
    email = f"life_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup",
                      json={"email": email, "password": "testpass123", "name": "Life"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    r2 = requests.post(f"{API}/billing/mock-unlock",
                       headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 200
    assert r2.json().get("plan") == "lifetime"
    return {"email": email, "token": tok}


@pytest.fixture(scope="module")
def life_headers(lifetime_user):
    return {"Authorization": f"Bearer {lifetime_user['token']}"}


# ================= 409 guards for lifetime users =================
def test_stripe_checkout_lifetime_returns_409(life_headers):
    r = requests.post(f"{API}/billing/checkout",
                      json={"origin_url": "https://example.com"},
                      headers=life_headers)
    assert r.status_code == 409, r.text
    assert r.json().get("detail") == EXPECTED_MSG


def test_razorpay_order_lifetime_returns_409(life_headers):
    r = requests.post(f"{API}/billing/razorpay/order",
                      json={"amount": 100, "currency": "INR"},
                      headers=life_headers)
    assert r.status_code == 409, r.text
    assert r.json().get("detail") == EXPECTED_MSG


def test_paypal_order_lifetime_returns_409_before_availability(life_headers):
    """Guard must run BEFORE the paypal_available() 503 check."""
    r = requests.post(f"{API}/billing/paypal/order",
                      json={"amount": 1.0, "currency": "USD"},
                      headers=life_headers)
    assert r.status_code == 409, r.text
    assert r.json().get("detail") == EXPECTED_MSG


# ================= Fresh free user regression =================
def test_stripe_checkout_free_user_returns_url(free_headers):
    r = requests.post(f"{API}/billing/checkout",
                      json={"origin_url": "https://example.com"},
                      headers=free_headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "url" in data
    # Real Stripe or mock — must be a URL
    assert data["url"].startswith("http")
    # If real stripe key is set, expect checkout.stripe.com
    if not data.get("mock"):
        assert "stripe.com" in data["url"], data


def test_razorpay_order_free_user_returns_order():
    """Fresh free user (not the one used in stripe test to avoid plan-flip)."""
    email = f"rzpfree_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup",
                      json={"email": email, "password": "testpass123", "name": "R"})
    assert r.status_code == 200
    tok = r.json()["token"]
    r2 = requests.post(f"{API}/billing/razorpay/order",
                       json={"amount": 100, "currency": "INR"},
                       headers={"Authorization": f"Bearer {tok}"})
    # Razorpay keys set in env — expect 200 order, else skip
    if r2.status_code == 503:
        pytest.skip("Razorpay not configured")
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data.get("order_id", "").startswith("order_")
    assert data.get("amount") == 100
    assert data.get("currency") == "INR"


def test_paypal_order_free_user_returns_503_when_unconfigured():
    """PayPal unconfigured → 503 for free user (proving guard order is 409-first for lifetime)."""
    email = f"ppfree_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup",
                      json={"email": email, "password": "testpass123", "name": "P"})
    tok = r.json()["token"]
    r2 = requests.post(f"{API}/billing/paypal/order",
                       json={"amount": 1.0, "currency": "USD"},
                       headers={"Authorization": f"Bearer {tok}"})
    # If PayPal is configured, expect 200; otherwise 503
    avail = requests.get(f"{API}/billing/paypal/available").json().get("available")
    if avail:
        assert r2.status_code == 200
    else:
        assert r2.status_code == 503, r2.text


# ================= mock-unlock idempotency =================
def test_mock_unlock_idempotent_for_lifetime(life_headers):
    r = requests.post(f"{API}/billing/mock-unlock", headers=life_headers)
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("already") is True
    assert data.get("plan") == "lifetime"


def test_mock_unlock_flips_free_user():
    email = f"mock_{uuid.uuid4().hex[:8]}@ughpdf.com"
    r = requests.post(f"{API}/auth/signup",
                      json={"email": email, "password": "testpass123", "name": "M"})
    tok = r.json()["token"]
    r2 = requests.post(f"{API}/billing/mock-unlock",
                       headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 200
    data = r2.json()
    assert data.get("ok") is True
    assert data.get("plan") == "lifetime"
    assert data.get("already") is not True


# ================= /billing/methods & availability regression =================
def test_billing_methods_lists_three_gateways():
    r = requests.get(f"{API}/billing/methods")
    assert r.status_code == 200
    data = r.json()
    ids = {g["id"] for g in data.get("gateways", [])}
    assert {"stripe", "razorpay", "paypal"}.issubset(ids)


def test_razorpay_available_true():
    r = requests.get(f"{API}/billing/razorpay/available")
    assert r.status_code == 200
    assert r.json().get("available") is True


def test_paypal_available_false():
    r = requests.get(f"{API}/billing/paypal/available")
    assert r.status_code == 200
    assert r.json().get("available") is False
