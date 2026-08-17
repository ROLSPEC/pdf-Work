import { Link } from "react-router-dom";
import { Sparkle, Lock, Cloud } from "@phosphor-icons/react";

// Inline style safeguards — some HSL vars weren't being picked up by Tailwind JIT
const CAT_STYLES = {
  convert:  { bg: "hsl(216 100% 74% / 0.4)",  fg: "hsl(var(--foreground))" },
  organize: { bg: "hsl(71 88% 54% / 0.4)",    fg: "hsl(var(--foreground))" },
  optimize: { bg: "hsl(45 100% 60% / 0.5)",   fg: "hsl(var(--foreground))" },
  edit:     { bg: "hsl(268 63% 60% / 0.35)",  fg: "hsl(var(--foreground))" },
  security: { bg: "hsl(10 100% 63% / 0.3)",   fg: "hsl(var(--foreground))" },
  ai:       { bg: "hsl(10 100% 63%)",         fg: "hsl(0 0% 100%)" },
};

const PLAN_TAG = (tool) => {
  // AI tools require credits (free tier gets 5/mo)
  if (tool.engine === "ai") return { label: `${tool.credits} cr`, cls: "bg-black text-white" };
  // Server tools work on free (uses daily ops quota)
  if (tool.engine === "server") return { label: "cloud", cls: "" };
  return { label: "free", cls: "" };
};

export default function ToolCard({ tool }) {
  const s = CAT_STYLES[tool.cat] || { bg: "hsl(var(--card))", fg: "hsl(var(--foreground))" };
  const tag = PLAN_TAG(tool);
  return (
    <Link
      to={`/t/${tool.id}`}
      data-testid={`tool-${tool.id}`}
      style={{ backgroundColor: s.bg, color: s.fg }}
      className="group brut brut-hover relative flex flex-col justify-between p-4 h-36"
    >
      <div className="flex items-start justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest font-bold">
          {tool.cat === "ai" ? "★ ai" : tool.cat}
        </span>
        <span className="opacity-80">
          {tool.engine === "local" && <Lock size={14} weight="bold" title="Local" />}
          {tool.engine === "server" && <Cloud size={14} weight="bold" title="Cloud" />}
          {tool.engine === "ai" && <Sparkle size={14} weight="fill" title={`AI · ${tool.credits} credits`} />}
        </span>
      </div>
      <div>
        <div className="font-display text-lg leading-tight">{tool.name}</div>
        <div className="text-xs opacity-75 line-clamp-1 mt-1 font-medium">{tool.desc}</div>
      </div>
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wider font-mono font-bold">
        <span>
          {tool.engine === "local" && "🔒 local · free"}
          {tool.engine === "server" && "☁ cloud"}
          {tool.engine === "ai" && `★ ${tool.credits} credit${tool.credits > 1 ? "s" : ""}`}
        </span>
        <span className="opacity-0 group-hover:opacity-100 transition-opacity">→ open</span>
      </div>
    </Link>
  );
}
