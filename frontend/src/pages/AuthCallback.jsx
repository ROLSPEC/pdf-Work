import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";

export default function AuthCallback() {
  const nav = useNavigate();
  const { refresh } = useAuth();
  useEffect(() => {
    // Emergent OAuth appends #session_id=... to fragment; auth.jsx handles it on mount too.
    const hash = window.location.hash;
    const sid = hash.startsWith("#session_id=") ? hash.slice(12) : new URLSearchParams(window.location.search).get("session_id");
    if (!sid) { nav("/login"); return; }
    (async () => {
      try {
        const { data } = await api.post("/auth/google", { session_id: sid });
        setToken(data.token);
        await refresh();
        toast.success("Signed in with Google");
        nav("/");
      } catch (e) { toast.error("Google sign-in failed"); nav("/login"); }
    })();
  }, [nav, refresh]);
  return <div className="p-10 text-center text-muted-foreground">Signing you in…</div>;
}
