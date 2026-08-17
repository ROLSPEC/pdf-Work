import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { Check, Sparkle } from "@phosphor-icons/react";
import { toast } from "sonner";

const FEATURES_FREE = ["25MB file size", "10 files per day", "All non-AI tools", "5 AI credits / month"];
const FEATURES_PAID = ["100MB file size", "Unlimited non-AI tools", "50 AI credits / month", "BYOK — unlimited AI", "Priority processing"];

export default function Pricing() {
  const { user } = useAuth();
  const nav = useNavigate();

  const unlock = async () => {
    if (!user) { nav("/signup"); return; }
    try {
      const { data } = await api.post("/billing/checkout");
      if (data.mock) toast.success("Mock unlock: enjoy lifetime access (dev mode).");
      window.location.href = data.url;
    } catch { toast.error("Checkout failed"); }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-16 paper-grid">
      <div className="text-center max-w-2xl mx-auto">
        <div className="brut-chip inline-flex sticker-rotate-r btn-accent-ink" data-testid="pricing-chip">
          <Sparkle size={12} weight="fill" /> one coin. forever.
        </div>
        <h1 className="font-display text-5xl sm:text-6xl tracking-tighter mt-6">
          Pricing that respects your time.
        </h1>
        <p className="text-sm mt-4 font-medium">No monthly games. No hidden trial. $1 unlocks everything.</p>
      </div>

      <div className="grid md:grid-cols-2 gap-6 mt-12">
        <div className="brut bg-card p-8">
          <div className="brut-chip mb-4">free</div>
          <div className="font-display text-6xl tracking-tighter">$0</div>
          <ul className="space-y-2 mt-6">
            {FEATURES_FREE.map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm font-medium"><Check size={16} weight="bold" /> {f}</li>
            ))}
          </ul>
          <button
            className="w-full brut-sm brut-hover bg-card px-4 py-3 mt-6 font-mono text-xs uppercase tracking-widest font-bold disabled:opacity-40"
            disabled={!!user}
            onClick={() => nav("/signup")}
          >
            {user ? "You're on Free" : "Get started free"}
          </button>
        </div>

        <div className="brut bg-primary p-8 -rotate-1">
          <div className="brut-chip bg-card mb-4">best value</div>
          <div className="flex items-baseline gap-2">
            <div className="font-display text-6xl tracking-tighter">$1</div>
            <div className="font-mono text-xs uppercase tracking-widest font-bold">one-time</div>
          </div>
          <ul className="space-y-2 mt-6">
            {FEATURES_PAID.map((f) => (
              <li key={f} className="flex items-center gap-2 text-sm font-bold"><Check size={16} weight="bold" /> {f}</li>
            ))}
          </ul>
          <button
            onClick={unlock}
            data-testid="unlock-btn"
            disabled={user?.plan === "lifetime"}
            className="w-full brut-sm brut-hover btn-ink px-4 py-3 mt-6 font-mono text-xs uppercase tracking-widest font-bold disabled:opacity-40"
          >
            {user?.plan === "lifetime" ? "You're a lifer 🎉" : "Unlock lifetime"}
          </button>
          <p className="text-[10px] font-mono uppercase tracking-widest text-center mt-3">$1 / ₹1 / £1 / €1 · geo-priced</p>
        </div>
      </div>
    </div>
  );
}
