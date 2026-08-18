import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { Sun, Moon, SignOut, UserCircle } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

export default function Header() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [dark, setDark] = useState(() => localStorage.getItem("ughpdf_theme") === "dark");
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("ughpdf_theme", dark ? "dark" : "light");
  }, [dark]);

  return (
    <header className="sticky top-0 z-40 border-b-2 border-border bg-background">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" data-testid="brand-link" className="flex items-center gap-2 group">
          <span className="inline-flex items-center justify-center w-9 h-9 brut-sm bg-primary text-primary-foreground font-display text-lg group-hover:sticker-rotate-l transition-transform">
            !
          </span>
          <span className="font-display text-2xl leading-none">
            Ugh<span className="text-accent">!</span>PDF
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-1 text-sm font-medium">
          {[
            { p: "/", label: "Tools", tid: "nav-tools" },
            { p: "/pricing", label: "Pricing", tid: "nav-pricing" },
            user && { p: "/dashboard", label: "Dashboard", tid: "nav-dashboard" },
          ].filter(Boolean).map((n) => (
            <Link key={n.p} to={n.p} data-testid={n.tid}
              className={`px-3 py-1.5 uppercase tracking-wider text-xs font-mono font-bold border-2 border-transparent hover:border-border ${loc.pathname === n.p ? "bg-primary border-border text-primary-foreground" : ""}`}
            >
              {n.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <button onClick={() => setDark(!dark)} data-testid="theme-toggle"
            className="w-9 h-9 brut-sm brut-hover flex items-center justify-center bg-card">
            {dark ? <Sun size={16} weight="bold" /> : <Moon size={16} weight="bold" />}
          </button>
          {!user ? (
            <>
              <button onClick={() => nav("/login")} data-testid="header-login"
                className="px-4 py-2 font-mono text-xs uppercase tracking-wider font-bold hover:underline underline-offset-4">
                Log in
              </button>
              <button onClick={() => nav("/signup")} data-testid="header-signup"
                className="px-4 py-2 brut-sm brut-hover bg-primary text-primary-foreground font-mono text-xs uppercase tracking-wider font-bold">
                Sign up · Free
              </button>
            </>
          ) : (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button data-testid="user-menu-trigger"
                  className="px-3 py-2 brut-sm brut-hover bg-card font-mono text-xs uppercase tracking-wider font-bold flex items-center gap-2">
                  <UserCircle size={16} weight="bold" /> {user.name}
                  {user.plan === "lifetime" && <span className="px-1.5 py-0.5 btn-accent-ink text-[10px]">PRO</span>}
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56 brut rounded-none border-2">
                <DropdownMenuLabel>
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground font-mono">Signed in</div>
                  <div className="truncate">{user.email}</div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => nav("/dashboard")} data-testid="menu-dashboard" className="font-mono text-xs uppercase tracking-wider">
                  Dashboard · {user.ops_today} ops today
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => nav("/pricing")} data-testid="menu-pricing" className="font-mono text-xs uppercase tracking-wider">
                  Billing
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => { logout(); nav("/"); }} data-testid="menu-logout" className="font-mono text-xs uppercase tracking-wider">
                  <SignOut size={14} className="mr-2" weight="bold" /> Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </header>
  );
}
