import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { CheckCircle } from "@phosphor-icons/react";

export default function Unlocked() {
  const nav = useNavigate();
  const { refresh } = useAuth();
  useEffect(() => {
    refresh().then(() => toast.success("Lifetime unlocked — welcome to the club."));
  }, [refresh]);
  return (
    <div className="max-w-xl mx-auto px-6 py-20 text-center">
      <div className="brut bg-primary p-10 sticker-rotate-l inline-block">
        <CheckCircle size={72} weight="bold" className="mx-auto text-primary-foreground" />
      </div>
      <h1 className="font-display text-5xl tracking-tighter mt-8">You're a lifer! 🎉</h1>
      <p className="text-sm mt-3 font-medium">All 52 tools + 50 AI credits/month. Go make magic.</p>
      <div className="flex gap-3 justify-center mt-8">
        <button onClick={() => nav("/dashboard")} data-testid="unlocked-dashboard"
          className="brut-sm brut-hover btn-ink px-5 py-3 font-mono text-xs uppercase tracking-widest font-bold">
          Go to dashboard
        </button>
        <button onClick={() => nav("/")}
          className="brut-sm brut-hover bg-card px-5 py-3 font-mono text-xs uppercase tracking-widest font-bold">
          Back to tools
        </button>
      </div>
    </div>
  );
}
