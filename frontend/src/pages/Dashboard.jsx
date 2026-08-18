import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useNavigate, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Lightning, Files, Trash, ArrowRight, Clock } from "@phosphor-icons/react";

function fmtBytes(n) {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0, v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v >= 10 ? 0 : 1)} ${u[i]}`;
}

function fmtRelative(iso) {
  const d = new Date(iso);
  const now = new Date();
  const diff = (d - now) / 1000; // seconds
  const abs = Math.abs(diff);
  if (abs < 60) return "just now";
  if (abs < 3600) return `${Math.round(abs / 60)}m ${diff < 0 ? "ago" : "left"}`;
  const h = abs / 3600;
  if (h < 24) return `${h.toFixed(0)}h ${diff < 0 ? "ago" : "left"}`;
  return d.toLocaleString();
}

export default function Dashboard() {
  const { user, loading: authLoading, refresh } = useAuth();
  const nav = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [ttl, setTtl] = useState(24);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/user/jobs");
      setJobs(data.jobs || []);
      setTtl(data.ttl_hours || 24);
    } catch (e) {
      // silent
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { nav("/login"); return; }
    load();
    // refresh every 30s so ttl countdown stays live
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, [user, authLoading, nav, load]);

  if (!user) return null;

  const deleteOne = async (id) => {
    try {
      await api.delete(`/user/jobs/${id}`);
      setJobs((js) => js.filter((j) => j.id !== id));
      toast.success("Deleted");
    } catch { toast.error("Failed to delete"); }
  };

  const deleteAll = async () => {
    if (!confirm("Delete your entire history? This can't be undone.")) return;
    try {
      const { data } = await api.delete("/user/jobs");
      setJobs([]);
      toast.success(`Deleted ${data.deleted} record${data.deleted === 1 ? "" : "s"}`);
    } catch { toast.error("Failed to delete history"); }
  };

  return (
    <div className="max-w-6xl mx-auto px-6 py-10">
      <div className="brut-chip mb-4">· dashboard ·</div>
      <h1 className="font-display text-5xl tracking-tighter" data-testid="dashboard-title">Yo, {user.name}.</h1>
      <p className="text-sm mt-2 font-medium">Your plan, usage and recent activity.</p>

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
        <Stat icon={<Lightning size={16} weight="fill" />} label="Ops today" bg="bg-primary/40">
          <div className="font-display text-4xl" data-testid="dashboard-ops">{user.ops_today}</div>
          <p className="text-[10px] font-mono uppercase tracking-widest mt-1">
            limit {user.daily_ops_limit}/day
          </p>
        </Stat>
        <Stat icon={<Clock size={16} weight="bold" />} label="File TTL" bg="bg-card">
          <div className="font-display text-4xl">{ttl}h</div>
          <p className="text-[10px] font-mono uppercase tracking-widest mt-1">auto-delete window</p>
        </Stat>
      </div>

      <div className="brut bg-card p-6 mt-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="brut-chip mb-2">· recent files ·</div>
            <h2 className="font-display text-2xl tracking-tighter">Your last 24 hours</h2>
            <p className="text-xs font-medium text-muted-foreground mt-1">
              We only store metadata (filename, tool, timestamp). The bytes are gone.
              Anything older than {ttl}h auto-deletes.
            </p>
          </div>
          {jobs.length > 0 && (
            <button onClick={deleteAll} data-testid="delete-all-btn"
              className="brut-sm brut-hover btn-accent-ink px-4 py-2 font-mono text-xs uppercase tracking-widest font-bold flex items-center gap-2">
              <Trash size={14} weight="bold" /> Delete all
            </button>
          )}
        </div>

        {loading ? (
          <p className="text-sm font-medium text-muted-foreground">Loading…</p>
        ) : jobs.length === 0 ? (
          <div className="brut-sm bg-primary/20 p-8 text-center">
            <div className="font-display text-2xl">Nothing here yet.</div>
            <p className="text-sm font-medium mt-1">Run a tool and your history will show up here.</p>
            <Link to="/" className="inline-flex items-center gap-1 mt-3 font-mono text-xs uppercase tracking-widest font-bold hover:underline">
              Browse tools <ArrowRight size={12} weight="bold" />
            </Link>
          </div>
        ) : (
          <ul className="divide-y-2 divide-border border-2 border-border" data-testid="jobs-list">
            {jobs.map((j) => (
              <li key={j.id} className="flex items-center justify-between p-3 gap-3" data-testid={`job-${j.id}`}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="brut-chip bg-card text-[9px]">{j.tool_id}</span>
                    <span className="font-medium truncate text-sm">{j.filename}</span>
                  </div>
                  <div className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground mt-1">
                    {fmtBytes(j.size_bytes)} · ran {fmtRelative(j.created_at)} · expires {fmtRelative(j.expires_at)}
                  </div>
                </div>
                <button onClick={() => deleteOne(j.id)} data-testid={`del-job-${j.id}`}
                  className="brut-sm brut-hover btn-accent-ink px-3 py-2 font-mono text-[10px] uppercase tracking-widest font-bold flex items-center gap-1">
                  <Trash size={12} weight="bold" /> Delete
                </button>
              </li>
            ))}
          </ul>
        )}
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
