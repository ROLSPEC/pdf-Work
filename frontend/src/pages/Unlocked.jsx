import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { CheckCircle, CircleNotch } from "@phosphor-icons/react";

export default function Unlocked() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const { refresh } = useAuth();
  const [state, setState] = useState("checking"); // checking | paid | mock | failed

  useEffect(() => {
    const sid = params.get("session_id");
    const mock = params.get("mock");
    if (mock === "1") {
      refresh().then(() => { setState("mock"); toast.success("Lifetime unlocked (dev/mock)."); });
      return;
    }
    if (!sid) { setState("paid"); refresh(); return; }
    // Poll status until paid or 15 attempts
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const { data } = await api.get(`/payments/status/${sid}`);
        if (data.payment_status === "paid") {
          clearInterval(interval);
          await refresh();
          setState("paid");
          toast.success("Lifetime unlocked — welcome to the club.");
        } else if (attempts >= 15) {
          clearInterval(interval);
          setState("failed");
          toast.error("Payment is taking longer than usual. Refresh in a minute.");
        }
      } catch {
        if (attempts >= 15) {
          clearInterval(interval);
          setState("failed");
        }
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [params, refresh]);

  return (
    <div className="max-w-xl mx-auto px-6 py-20 text-center">
      {state === "checking" ? (
        <>
          <div className="brut bg-card p-10 inline-block">
            <CircleNotch size={56} weight="bold" className="mx-auto animate-spin" />
          </div>
          <h1 className="font-display text-4xl tracking-tighter mt-8">Confirming payment…</h1>
          <p className="text-sm mt-3 font-medium">Hang tight — this usually takes 2-5 seconds.</p>
        </>
      ) : state === "failed" ? (
        <>
          <div className="brut bg-destructive/10 border-destructive p-8 inline-block">
            <h2 className="font-display text-3xl tracking-tighter">Still processing…</h2>
            <p className="text-sm mt-2 font-medium">Payment received but syncing is slow. Try refreshing your dashboard in a minute.</p>
          </div>
          <div className="flex gap-3 justify-center mt-6">
            <button onClick={() => nav("/dashboard")} className="brut-sm brut-hover btn-ink px-5 py-3 font-mono text-xs uppercase tracking-widest font-bold">Go to dashboard</button>
          </div>
        </>
      ) : (
        <>
          <div className="brut bg-primary p-10 sticker-rotate-l inline-block">
            <CheckCircle size={72} weight="bold" className="mx-auto text-primary-foreground" />
          </div>
          <h1 className="font-display text-5xl tracking-tighter mt-8">You're a lifer! 🎉</h1>
          <p className="text-sm mt-3 font-medium">All 45 tools, 100 MB uploads, unlimited runs. Go make magic.</p>
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
        </>
      )}
    </div>
  );
}
