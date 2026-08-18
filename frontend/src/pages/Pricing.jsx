import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Check, X, CreditCard } from "@phosphor-icons/react";
import { toast } from "sonner";

const FEATURES_FREE = [
  { text: "All 12 in-browser tools · unlimited", ok: true },
  { text: "25 MB max file size", ok: true },
  { text: "10 cloud ops / day", ok: true },
  { text: "24-hour auto-delete of history", ok: true },
  { text: "100 MB max file size", ok: false },
  { text: "200 cloud ops / day", ok: false },
  { text: "Priority processing queue", ok: false },
  { text: "Support the project ❤️", ok: false },
];

const FEATURES_PAID = [
  { text: "Everything in Free, plus…", ok: true },
  { text: "100 MB max file size", ok: true },
  { text: "200 cloud ops / day (basically unlimited)", ok: true },
  { text: "Priority processing queue", ok: true },
  { text: "Support the project ❤️", ok: true },
  { text: "One-time · geo-priced", ok: true },
  { text: "No renewals. Ever.", ok: true },
  { text: "One coin. Forever.", ok: true },
];

function loadScript(src) {
  return new Promise((res, rej) => {
    if (document.querySelector(`script[src="${src}"]`)) return res();
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => res();
    s.onerror = () => rej(new Error("Failed to load " + src));
    document.body.appendChild(s);
  });
}

export default function Pricing() {
  const { user, refresh } = useAuth();
  const nav = useNavigate();
  const [methods, setMethods] = useState({
    country: "US", currency: "USD", symbol: "$", display: "$1", recommended: "stripe",
    gateways: [
      { id: "stripe", name: "Stripe", available: true, methods: ["card"], currencies: ["USD"] },
      { id: "razorpay", name: "Razorpay", available: false, methods: [], currencies: ["INR"] },
    ],
  });
  const [gateway, setGateway] = useState("stripe");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/billing/methods").then(({ data }) => {
      setMethods(data);
      if (data.recommended) setGateway(data.recommended);
    }).catch(() => {});
  }, []);

  const unlockStripe = async () => {
    const { data } = await api.post("/billing/checkout", { origin_url: window.location.origin });
    if (data.mock) toast.success("Mock unlock (dev)");
    window.location.href = data.url;
  };

  const unlockRazorpay = async () => {
    await loadScript("https://checkout.razorpay.com/v1/checkout.js");
    const { data: order } = await api.post("/billing/razorpay/order", { amount: 100, currency: "INR" });
    return new Promise((resolve, reject) => {
      const rzp = new window.Razorpay({
        key: order.key_id,
        amount: order.amount,
        currency: order.currency,
        order_id: order.order_id,
        name: "Ugh!PDF",
        description: "Lifetime unlock",
        prefill: { name: user?.name || "", email: user?.email || "" },
        theme: { color: "#F5E642" },
        modal: { ondismiss: () => reject(new Error("Payment cancelled")) },
        handler: async (resp) => {
          try {
            await api.post("/billing/razorpay/verify", {
              razorpay_order_id: resp.razorpay_order_id,
              razorpay_payment_id: resp.razorpay_payment_id,
              razorpay_signature: resp.razorpay_signature,
            });
            await refresh();
            toast.success("You're a lifer! 🎉");
            nav("/unlocked");
            resolve();
          } catch (e) {
            toast.error("Verify failed: " + (e?.response?.data?.detail || e.message));
            reject(e);
          }
        },
      });
      rzp.open();
    });
  };

  const unlock = async () => {
    if (!user) { nav("/signup"); return; }
    setBusy(true);
    try {
      if (gateway === "razorpay") await unlockRazorpay();
      else await unlockStripe();
    } catch (e) {
      if (e?.message !== "Payment cancelled") toast.error(e?.response?.data?.detail || "Checkout failed");
    } finally { setBusy(false); }
  };

  const stripeCard = methods.gateways.find((g) => g.id === "stripe");
  const razorpayCard = methods.gateways.find((g) => g.id === "razorpay");

  return (
    <div className="max-w-5xl mx-auto px-6 py-16 paper-grid">
      <div className="text-center max-w-2xl mx-auto">
        <div className="brut-chip inline-flex sticker-rotate-r btn-accent-ink" data-testid="pricing-chip">
          one coin. forever.
        </div>
        <h1 className="font-display text-5xl sm:text-6xl tracking-tighter mt-6">
          Pricing that respects your time.
        </h1>
        <p className="text-sm mt-4 font-medium">
          No monthly games. No hidden trial. <b>{methods.display}</b> unlocks everything.
        </p>
        <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mt-2" data-testid="geo-detected">
          detected · {methods.country} · pay in {methods.currency}
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-6 mt-12">
        <div className="brut bg-card p-8" data-testid="free-card">
          <div className="brut-chip mb-4">free · always</div>
          <div className="font-display text-6xl tracking-tighter">$0</div>
          <p className="text-xs font-mono uppercase tracking-widest mt-2">forever · no card</p>
          <ul className="space-y-2 mt-6">
            {FEATURES_FREE.map((f, i) => (
              <li key={i} className={`flex items-start gap-2 text-sm font-medium ${!f.ok ? "opacity-40 line-through" : ""}`}>
                {f.ok ? <Check size={16} weight="bold" className="mt-0.5" /> : <X size={16} weight="bold" className="mt-0.5" />}
                {f.text}
              </li>
            ))}
          </ul>
          <button
            className="w-full brut-sm brut-hover bg-card px-4 py-3 mt-6 font-mono text-xs uppercase tracking-widest font-bold disabled:opacity-40"
            disabled={!!user} onClick={() => nav("/signup")} data-testid="free-cta"
          >
            {user ? "You're on Free" : "Get started free"}
          </button>
        </div>

        <div className="brut btn-primary-ink p-8 -rotate-1" data-testid="paid-card">
          <div className="brut-chip bg-card mb-4">best value</div>
          <div className="flex items-baseline gap-2">
            <div className="font-display text-6xl tracking-tighter" data-testid="paid-price">{methods.display}</div>
            <div className="font-mono text-xs uppercase tracking-widest font-bold">one-time · {methods.currency}</div>
          </div>
          <p className="text-xs font-mono uppercase tracking-widest mt-2">lifetime · no renewals · no upsells</p>
          <ul className="space-y-2 mt-6">
            {FEATURES_PAID.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-sm font-bold">
                <Check size={16} weight="bold" className="mt-0.5" /> {f.text}
              </li>
            ))}
          </ul>

          {/* Payment gateway selector */}
          <div className="mt-6 space-y-2" data-testid="gateway-selector">
            <div className="text-[10px] font-mono uppercase tracking-widest font-bold">Pay with</div>
            <div className="grid grid-cols-2 gap-2">
              <GatewayOption
                id="stripe" name="Stripe" available={stripeCard?.available}
                methods={stripeCard?.methods || []} selected={gateway === "stripe"}
                onClick={() => setGateway("stripe")} testId="opt-stripe"
              />
              <GatewayOption
                id="razorpay" name="Razorpay" available={razorpayCard?.available}
                methods={razorpayCard?.methods || []} selected={gateway === "razorpay"}
                onClick={() => setGateway("razorpay")} testId="opt-razorpay"
              />
            </div>
            {!razorpayCard?.available && (
              <p className="text-[10px] font-mono uppercase tracking-widest opacity-80" data-testid="razorpay-unavailable">
                Razorpay not configured on this server — Stripe will be used
              </p>
            )}
          </div>

          <button
            onClick={unlock}
            data-testid="unlock-btn"
            disabled={user?.plan === "lifetime" || busy}
            className="w-full brut-sm brut-hover btn-ink px-4 py-3 mt-4 font-mono text-xs uppercase tracking-widest font-bold disabled:opacity-40"
          >
            {user?.plan === "lifetime" ? "You're a lifer 🎉" : (busy ? "…" : `Unlock lifetime · ${methods.display}`)}
          </button>
          <p className="text-[10px] font-mono uppercase tracking-widest text-center mt-3">
            Stripe: $1 · £1 · €1 · C$1 · A$1 · NZ$1 · Razorpay: ₹1 UPI · Card
          </p>
        </div>
      </div>

      <div className="mt-16 grid md:grid-cols-3 gap-4">
        <FAQ q="Why so cheap?" a="We want you to stop hitting paywalls. $1 covers our server long enough for you to fall in love and tell friends." />
        <FAQ q="Which gateway do you use?" a="Stripe for cards / Apple Pay / Google Pay worldwide, Razorpay for UPI + Indian cards. Auto-detected from your country." />
        <FAQ q="Do you keep my files?" a="No. Files are never permanently stored. We only keep a metadata trail for 24 hours so you can see recent activity — delete any time." />
      </div>
    </div>
  );
}

function GatewayOption({ id, name, available, methods, selected, onClick, testId }) {
  const dim = !available;
  return (
    <button
      onClick={onClick}
      disabled={dim}
      data-testid={testId}
      className={`brut-sm text-left px-3 py-2 font-mono text-[11px] uppercase tracking-widest font-bold flex flex-col gap-1 ${selected ? "btn-ink" : "bg-card"} ${dim ? "opacity-50" : ""}`}
    >
      <span className="flex items-center gap-1">
        <CreditCard size={12} weight="bold" /> {name} {selected && "✓"}
      </span>
      <span className="text-[9px] normal-case tracking-wide opacity-80 truncate">
        {available ? methods.slice(0, 3).join(" · ") : "unavailable"}
      </span>
    </button>
  );
}

function FAQ({ q, a }) {
  return (
    <div className="brut-sm bg-card p-4">
      <div className="font-display text-lg tracking-tighter">{q}</div>
      <p className="text-xs mt-2 font-medium">{a}</p>
    </div>
  );
}
