import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { GoogleLogo } from "@phosphor-icons/react";

export default function Auth({ mode = "login" }) {
  const nav = useNavigate();
  const { login, signup, loginWithGoogle } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const isSignup = mode === "signup";

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (isSignup) await signup(email, password, name);
      else await login(email, password);
      toast.success(isSignup ? "Welcome to Ugh!PDF" : "Welcome back");
      nav("/");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Auth failed");
    } finally { setBusy(false); }
  };

  const inputCls = "mt-1.5 rounded-none border-2 border-border font-mono";

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-6 py-12 paper-grid">
      <div className="w-full max-w-md brut bg-card p-8" data-testid="auth-card">
        <div className="brut-chip mb-6 sticker-rotate-l inline-flex">
          {isSignup ? "· new here ·" : "· welcome back ·"}
        </div>
        <h1 className="font-display text-4xl tracking-tighter">
          {isSignup ? "Sign up." : "Log in."}
        </h1>
        <p className="text-sm mt-2 font-medium">
          {isSignup ? "Free tier: 25MB, 10 files/day." : "Log in to use cloud tools & see your recent files."}
        </p>

        <button
          onClick={loginWithGoogle}
          data-testid="google-login"
          className="w-full brut-sm brut-hover mt-6 bg-card px-4 py-3 font-mono text-xs uppercase tracking-widest font-bold flex items-center justify-center gap-2"
        >
          <GoogleLogo size={18} weight="bold" /> Continue with Google
        </button>

        <div className="my-5 flex items-center gap-3 text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
          <div className="h-0.5 flex-1 bg-border" />or email<div className="h-0.5 flex-1 bg-border" />
        </div>

        <form onSubmit={submit} className="space-y-3">
          {isSignup && (
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-widest font-bold">Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} data-testid="auth-name" />
            </div>
          )}
          <div>
            <Label className="text-[10px] font-mono uppercase tracking-widest font-bold">Email</Label>
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} data-testid="auth-email" />
          </div>
          <div>
            <Label className="text-[10px] font-mono uppercase tracking-widest font-bold">Password</Label>
            <Input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} data-testid="auth-password" />
          </div>
          <button
            type="submit"
            disabled={busy}
            data-testid="auth-submit"
            className="w-full brut-sm brut-hover bg-primary text-primary-foreground py-3 font-mono text-xs uppercase tracking-widest font-bold disabled:opacity-40"
          >
            {busy ? "…" : isSignup ? "Create account" : "Log in"}
          </button>
        </form>

        <p className="text-sm text-center mt-5 font-medium">
          {isSignup
            ? <>Already have an account? <Link to="/login" className="underline decoration-primary decoration-4 underline-offset-4" data-testid="switch-login">Log in</Link></>
            : <>New here? <Link to="/signup" className="underline decoration-primary decoration-4 underline-offset-4" data-testid="switch-signup">Create account</Link></>}
        </p>
      </div>
    </div>
  );
}
