import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Sparkle, Lightning, Files } from "@phosphor-icons/react";

export default function Dashboard() {
  const { user, refresh } = useAuth();
  const nav = useNavigate();
  const [openaiKey, setOpenaiKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");

  useEffect(() => { if (user === null) nav("/login"); }, [user, nav]);
  if (!user) return null;

  const saveKeys = async () => {
    try {
      await api.post("/auth/byok", { openai_key: openaiKey || null, gemini_key: geminiKey || null });
      await refresh();
      toast.success("Keys saved");
      setOpenaiKey(""); setGeminiKey("");
    } catch { toast.error("Failed to save keys"); }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-10">
      <div className="brut-chip mb-4">· dashboard ·</div>
      <h1 className="font-display text-5xl tracking-tighter" data-testid="dashboard-title">Yo, {user.name}.</h1>
      <p className="text-sm mt-2 font-medium">Track your credits, plan, and BYOK settings.</p>

      <div className="grid md:grid-cols-3 gap-4 mt-8">
        <Stat icon={<Files size={16} weight="bold" />} label="Plan" bg="bg-card">
          <div className="font-display text-4xl" data-testid="dashboard-plan">
            {user.plan === "lifetime" ? "Lifetime" : "Free"}
          </div>
          {user.plan !== "lifetime" && (
            <button onClick={() => nav("/pricing")} data-testid="upgrade-btn"
              className="brut-sm brut-hover btn-accent-ink px-4 py-2 mt-3 font-mono text-xs uppercase tracking-widest font-bold">
              Unlock for $1
            </button>
          )}
        </Stat>
        <Stat icon={<Sparkle size={16} weight="fill" className="text-accent" />} label="AI credits" bg="bg-primary/30">
          <div className="font-display text-4xl" data-testid="dashboard-credits">{user.ai_credits}</div>
          <p className="text-[10px] font-mono uppercase tracking-widest mt-1">
            resets {new Date(user.ai_credits_reset_at).toLocaleDateString()}
          </p>
        </Stat>
        <Stat icon={<Lightning size={16} weight="fill" className="text-sun" />} label="Ops today" bg="bg-sun/40">
          <div className="font-display text-4xl" data-testid="dashboard-ops">{user.ops_today}</div>
          <p className="text-[10px] font-mono uppercase tracking-widest mt-1">
            limit {user.plan === "lifetime" ? 200 : 10}/day
          </p>
        </Stat>
      </div>

      <div className="brut bg-card p-6 mt-8">
        <div className="brut-chip mb-3">· byok ·</div>
        <h2 className="font-display text-2xl tracking-tighter">Bring Your Own Keys</h2>
        <p className="text-sm mt-1 font-medium">Out of credits? Plug your own OpenAI or Gemini key. Zero cost to us — unlimited to you.</p>

        <div className="flex gap-2 mt-4">
          <span className={`brut-chip ${user.byok_openai ? "bg-primary" : "bg-card"}`}>{user.byok_openai ? "✓ OpenAI" : "— OpenAI"}</span>
          <span className={`brut-chip ${user.byok_gemini ? "bg-primary" : "bg-card"}`}>{user.byok_gemini ? "✓ Gemini" : "— Gemini"}</span>
        </div>

        <div className="grid md:grid-cols-2 gap-3 mt-5">
          <div>
            <Label className="text-[10px] font-mono uppercase tracking-widest font-bold">OpenAI key</Label>
            <Input type="password" value={openaiKey} onChange={(e) => setOpenaiKey(e.target.value)} placeholder="sk-..." className="mt-1.5 rounded-none border-2 border-border font-mono" data-testid="byok-openai" />
          </div>
          <div>
            <Label className="text-[10px] font-mono uppercase tracking-widest font-bold">Gemini key</Label>
            <Input type="password" value={geminiKey} onChange={(e) => setGeminiKey(e.target.value)} placeholder="AIza..." className="mt-1.5 rounded-none border-2 border-border font-mono" data-testid="byok-gemini" />
          </div>
        </div>
        <button onClick={saveKeys} data-testid="save-keys"
          className="brut-sm brut-hover btn-ink px-5 py-2.5 mt-5 font-mono text-xs uppercase tracking-widest font-bold">
          Save keys
        </button>
      </div>
    </div>
  );
}

function Stat({ icon, label, bg, children }) {
  return (
    <div className={`brut p-5 ${bg}`}>
      <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest font-bold">
        {icon} {label}
      </div>
      <div className="mt-3">{children}</div>
    </div>
  );
}
