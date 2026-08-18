import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Check, X } from "@phosphor-icons/react";
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

export default function Pricing() {
  const { user } = useAuth();
  const nav = useNavigate();
  const [geo, setGeo] = useState({ display: "$1", currency: "USD", country: "US" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/billing/geo")
      .then(({ data }) => setGeo(data))
      .catch(() => {});
  }, []);

  const unlock = async () => {
    if (!user) { nav("/signup"); return; }
    setBusy(true);
    try {
      const { data } = await api.post("/billing/checkout", { origin_url: window.location.origin });
      if (data.mock) toast.success("Mock unlock: enjoy lifetime access (dev).");
      window.location.href = data.url;
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Checkout failed");
      setBusy(false);
    }
  };

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
          No monthly games. No hidden trial. <b>{geo.display}</b> unlocks everything.
        </p>
        <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mt-2" data-testid="geo-detected">
          detected · {geo.country} · pay in {geo.currency}
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
            disabled={!!user}
            onClick={() => nav("/signup")}
            data-testid="free-cta"
          >
            {user ? "You're on Free" : "Get started free"}
          </button>
        </div>

        <div className="brut btn-primary-ink p-8 -rotate-1" data-testid="paid-card">
          <div className="brut-chip bg-card mb-4">best value</div>
          <div className="flex items-baseline gap-2">
            <div className="font-display text-6xl tracking-tighter" data-testid="paid-price">{geo.display}</div>
            <div className="font-mono text-xs uppercase tracking-widest font-bold">one-time · {geo.currency}</div>
          </div>
          <p className="text-xs font-mono uppercase tracking-widest mt-2">lifetime · no renewals · no upsells</p>
          <ul className="space-y-2 mt-6">
            {FEATURES_PAID.map((f, i) => (
              <li key={i} className="flex items-start gap-2 text-sm font-bold">
                <Check size={16} weight="bold" className="mt-0.5" /> {f.text}
              </li>
            ))}
          </ul>
          <button
            onClick={unlock}
            data-testid="unlock-btn"
            disabled={user?.plan === "lifetime" || busy}
            className="w-full brut-sm brut-hover btn-ink px-4 py-3 mt-6 font-mono text-xs uppercase tracking-widest font-bold disabled:opacity-40"
          >
            {user?.plan === "lifetime" ? "You're a lifer 🎉" : (busy ? "…" : `Unlock lifetime · ${geo.display}`)}
          </button>
          <p className="text-[10px] font-mono uppercase tracking-widest text-center mt-3">
            $1 · £1 · €1 · ₹1 · C$1 · A$1 · NZ$1 · geo-priced
          </p>
        </div>
      </div>

      <div className="mt-16 grid md:grid-cols-3 gap-4">
        <FAQ q="Why so cheap?" a="We want you to stop hitting paywalls. $1 covers our server long enough for you to fall in love and tell friends." />
        <FAQ q="What's local vs cloud?" a="12 tools (merge, split, watermark, page numbers, etc.) run 100% in your browser — nothing leaves your device. The rest need our server; jobs auto-delete in 24h." />
        <FAQ q="Do you keep my files?" a="No. Files are never permanently stored. We only keep a metadata trail for 24 hours so you can see recent activity — and you can delete it any time." />
      </div>
    </div>
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
