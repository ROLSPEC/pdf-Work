import { Link } from "react-router-dom";
import { Lock, Cloud } from "@phosphor-icons/react";

// Inline style safeguards — some HSL vars weren't being picked up by Tailwind JIT
const CAT_STYLES = {
  convert:  { bg: "hsl(0 0% 100%)",           fg: "hsl(0 0% 7%)" },
  organize: { bg: "hsl(56 89% 61% / 0.55)",   fg: "hsl(0 0% 7%)" },
  optimize: { bg: "hsl(0 0% 100%)",           fg: "hsl(0 0% 7%)" },
  edit:     { bg: "hsl(56 89% 61% / 0.35)",   fg: "hsl(0 0% 7%)" },
  security: { bg: "hsl(3 100% 59% / 0.2)",    fg: "hsl(0 0% 7%)" },
  search:   { bg: "hsl(0 0% 7%)",             fg: "hsl(0 0% 100%)" },
};

export default function ToolCard({ tool }) {
  const s = CAT_STYLES[tool.cat] || { bg: "hsl(var(--card))", fg: "hsl(var(--foreground))" };
  return (
    <Link
      to={`/t/${tool.id}`}
      data-testid={`tool-${tool.id}`}
      style={{ backgroundColor: s.bg, color: s.fg }}
      className="group brut brut-hover relative flex flex-col justify-between p-4 h-36"
    >
      <div className="flex items-start justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest font-bold">{tool.cat}</span>
        <span className="opacity-80">
          {tool.engine === "local"
            ? <Lock size={14} weight="bold" title="Local" />
            : <Cloud size={14} weight="bold" title="Cloud" />}
        </span>
      </div>
      <div>
        <div className="font-display text-lg leading-tight">{tool.name}</div>
        <div className="text-xs opacity-75 line-clamp-1 mt-1 font-medium">{tool.desc}</div>
      </div>
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wider font-mono font-bold">
        <span>{tool.engine === "local" ? "🔒 local · free" : "☁ cloud · 24h"}</span>
        <span className="opacity-0 group-hover:opacity-100 transition-opacity">→ open</span>
      </div>
    </Link>
  );
}
