import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { TOOLS, CATEGORIES, TOOL_MAP } from "@/lib/tools";
import ToolCard from "@/components/ToolCard";
import DropZone from "@/components/DropZone";
import { MagnifyingGlass, Sparkle, ArrowRight, Lightning, ShieldCheck, Heart } from "@phosphor-icons/react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

const suggestForFile = (file) => {
  const n = (file?.name || "").toLowerCase();
  if (n.endsWith(".pdf")) return ["merge", "compress", "ai-chat", "ai-summarize"];
  if (/(jpe?g|png|heic)$/i.test(n)) return ["jpg-to-pdf", "id-card"];
  if (/(docx?|rtf)$/i.test(n)) return ["word-to-pdf"];
  if (/(xlsx?|csv)$/i.test(n)) return ["excel-to-pdf"];
  if (/(pptx?)$/i.test(n)) return ["ppt-to-pdf"];
  if (/(md|markdown)$/i.test(n)) return ["markdown-to-pdf"];
  if (/(html?)$/i.test(n)) return ["html-to-pdf"];
  return ["merge", "compress", "ai-chat"];
};

export default function Landing() {
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("all");
  const [dropped, setDropped] = useState(null);
  const nav = useNavigate();

  const filtered = useMemo(() => {
    const query = q.toLowerCase().trim();
    return TOOLS.filter((t) => (cat === "all" || t.cat === cat) &&
      (!query || t.name.toLowerCase().includes(query) || t.desc.toLowerCase().includes(query)));
  }, [q, cat]);

  const suggestions = dropped ? suggestForFile(dropped[0]).map((id) => TOOL_MAP[id]).filter(Boolean) : [];

  return (
    <div className="relative paper-grid">
      {/* HERO */}
      <section className="border-b-2 border-border">
        <div className="max-w-7xl mx-auto px-6 pt-16 pb-14">
          <div className="grid md:grid-cols-[1.2fr_1fr] gap-10 items-start">
            <div>
              <div className="brut-chip mb-6 sticker-rotate-l inline-flex" data-testid="hero-chip">
                <Sparkle size={12} weight="fill" /> 53 tools · $1 lifetime
              </div>
              <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl leading-[0.95] tracking-tighter">
                Every PDF task,<br />
                <span className="relative inline-block">
                  <span className="absolute -inset-1 -skew-y-2 bg-primary -z-0" aria-hidden />
                  <span className="relative">in one clean spot.</span>
                </span>
              </h1>
              <p className="text-lg mt-6 max-w-xl font-medium">
                Convert, sign, redact, and <span className="underline decoration-accent decoration-4 underline-offset-4">chat with your PDFs</span>.
                Half runs in your browser (private, instant). All 53 tools —
                for a <b className="bg-sun px-1.5 -mx-0.5 border-2 border-border">one-time $1</b>.
              </p>
              <div className="flex flex-wrap gap-3 mt-8">
                <button onClick={() => document.getElementById("tools-grid")?.scrollIntoView({ behavior: "smooth" })}
                  data-testid="cta-browse"
                  style={{ backgroundColor: 'hsl(var(--foreground))', color: 'hsl(var(--background))' }}
                  className="brut brut-hover px-6 py-3 font-mono text-xs uppercase tracking-widest font-bold flex items-center gap-2">
                  Browse 53 tools <ArrowRight size={14} weight="bold" />
                </button>
                <button onClick={() => nav("/pricing")}
                  data-testid="cta-unlock"
                  style={{ backgroundColor: 'hsl(var(--accent))', color: 'hsl(var(--accent-foreground))' }}
                  className="brut brut-hover px-6 py-3 font-mono text-xs uppercase tracking-widest font-bold">
                  Unlock lifetime · $1
                </button>
              </div>

              <div className="grid grid-cols-3 gap-3 mt-10 max-w-lg">
                <MiniFeature icon={<ShieldCheck size={18} weight="bold" />} label="12 tools stay local" />
                <MiniFeature icon={<Lightning size={18} weight="bold" />} label="No signup for basics" />
                <MiniFeature icon={<Heart size={18} weight="fill" />} label="No monthly games" />
              </div>
            </div>

            <div className="space-y-4">
              <DropZone
                multiple
                accept={{ "application/pdf": [".pdf"], "image/*": [".jpg", ".jpeg", ".png", ".heic"], "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"] }}
                onFiles={(files) => { setDropped(files); toast.success(`Got ${files.length} file(s). Pick a tool below.`); }}
                hint="any PDF, image, or Office file"
                testId="hero-dropzone"
              />
              <div className="brut-sm bg-card p-4">
                <div className="text-[10px] font-mono uppercase tracking-widest font-bold mb-2">↳ Suggestions</div>
                {!dropped ? (
                  <p className="text-sm text-muted-foreground">Drop a file, we'll pick 4 likely tools.</p>
                ) : (
                  <div className="space-y-2">
                    {suggestions.map((t) => (
                      <button
                        key={t.id}
                        data-testid={`suggest-${t.id}`}
                        onClick={() => nav(`/t/${t.id}`, { state: { file: dropped[0] } })}
                        className="w-full text-left px-3 py-2 border-2 border-border hover:bg-primary hover:text-primary-foreground transition-colors font-medium text-sm flex justify-between items-center"
                      >
                        <span>{t.name}</span>
                        <ArrowRight size={14} weight="bold" />
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* SEARCH + CATS */}
      <section id="tools-grid" className="max-w-7xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-6">
          <h2 className="font-display text-3xl tracking-tighter">The 53 tools →</h2>
          <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground">showing {filtered.length}</div>
        </div>

        <div className="brut-sm bg-card p-2 mb-5">
          <div className="flex flex-col md:flex-row gap-2">
            <div className="relative flex-1">
              <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2" weight="bold" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search — try 'compress' or 'chat'"
                className="pl-10 h-11 rounded-none border-2 border-transparent focus:border-border font-mono"
                data-testid="tool-search"
              />
            </div>
            <div className="flex gap-1.5 overflow-x-auto md:overflow-visible">
              {CATEGORIES.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setCat(c.id)}
                  data-testid={`cat-${c.id}`}
                  className={`whitespace-nowrap px-3 py-2 border-2 font-mono text-xs uppercase tracking-widest font-bold transition-colors ${cat === c.id ? "bg-foreground text-background border-border" : "bg-card border-border hover:bg-primary hover:text-primary-foreground"}`}
                >
                  {c.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4" data-testid="tool-grid">
          {filtered.map((t) => <ToolCard key={t.id} tool={t} />)}
        </div>
        {filtered.length === 0 && (
          <div className="brut-sm p-8 text-center animate-shake" data-testid="no-tools">
            <div className="font-display text-2xl">Ugh. No matches.</div>
            <p className="text-sm text-muted-foreground mt-1">Try another search term.</p>
          </div>
        )}
      </section>

      {/* WHY */}
      <section className="border-t-2 border-border bg-card">
        <div className="max-w-7xl mx-auto px-6 py-16 grid md:grid-cols-3 gap-6">
          <WhyCard label="private" tone="bg-primary/30" title="Half runs in your browser." desc="Merge, split, watermark and 9 more tools never upload your file. Zero server storage." />
          <WhyCard label="cheap" tone="bg-sun/60" title="$1 lifetime. No trial games." desc="Unlock every tool + 50 monthly AI credits for a single coin. Really." />
          <WhyCard label="smart" tone="bg-accent/30" title="AI you'd actually use." desc="Chat with any PDF, extract invoices to JSON, or turn a book into an audiobook." />
        </div>
      </section>

      {/* PLAN COMPARE */}
      <section className="border-t-2 border-border">
        <div className="max-w-7xl mx-auto px-6 py-16">
          <div className="text-center max-w-2xl mx-auto mb-8">
            <div className="brut-chip inline-flex">· free vs paid ·</div>
            <h2 className="font-display text-4xl tracking-tighter mt-4">What you get on each plan.</h2>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="brut bg-card p-6">
              <div className="flex items-baseline justify-between">
                <div className="font-display text-3xl tracking-tighter">Free</div>
                <div className="font-display text-3xl">$0</div>
              </div>
              <ul className="mt-4 space-y-2 text-sm font-medium">
                <li>✓ All 12 in-browser tools · unlimited</li>
                <li>✓ 25MB max file size</li>
                <li>✓ 10 cloud ops / day</li>
                <li>✓ 5 AI credits / month</li>
                <li className="opacity-50">✗ 100MB files / 200 ops-day</li>
                <li className="opacity-50">✗ 50 AI credits / month</li>
                <li className="opacity-50">✗ BYOK unlimited AI</li>
              </ul>
            </div>
            <div className="brut btn-primary-ink p-6" data-testid="landing-paid-card">
              <div className="flex items-baseline justify-between">
                <div className="font-display text-3xl tracking-tighter">Lifetime</div>
                <div className="font-display text-3xl">$1</div>
              </div>
              <ul className="mt-4 space-y-2 text-sm font-bold">
                <li>✓ Everything in Free, plus…</li>
                <li>✓ 100MB max file size</li>
                <li>✓ 200 cloud ops / day (basically unlimited)</li>
                <li>✓ 50 AI credits / month (auto-refill)</li>
                <li>✓ BYOK — unlimited AI, zero cost</li>
                <li>✓ Priority processing</li>
                <li>✓ One-time · geo-priced ($1 / £1 / €1 / ₹1…)</li>
              </ul>
              <button onClick={() => nav("/pricing")}
                data-testid="landing-unlock-cta"
                className="w-full brut-sm brut-hover btn-ink mt-5 px-4 py-3 font-mono text-xs uppercase tracking-widest font-bold">
                See pricing →
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function MiniFeature({ icon, label }) {
  return (
    <div className="brut-sm bg-card p-3 flex items-center gap-2">
      <span className="text-accent">{icon}</span>
      <span className="text-xs font-medium leading-tight">{label}</span>
    </div>
  );
}
function WhyCard({ label, tone, title, desc }) {
  return (
    <div className={`brut p-6 ${tone}`}>
      <div className="brut-chip bg-background mb-4">{label}</div>
      <h3 className="font-display text-2xl leading-tight">{title}</h3>
      <p className="text-sm mt-2 font-medium">{desc}</p>
    </div>
  );
}
