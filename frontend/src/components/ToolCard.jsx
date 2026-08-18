import { Link } from "react-router-dom";
import { Lock, Cloud } from "@phosphor-icons/react";

// Inline style safeguards — some HSL vars weren't being picked up by Tailwind JIT
// On-brand pastel tints per category (opaque so they read well in light AND dark mode)
const CAT_STYLES = {
  convert:  { bg: "hsl(243 80% 93%)",  fg: "hsl(243 60% 20%)" },  // indigo
  organize: { bg: "hsl(160 62% 85%)",  fg: "hsl(160 70% 15%)" },  // emerald
  optimize: { bg: "hsl(38 92% 84%)",   fg: "hsl(28 80% 20%)" },   // amber
  edit:     { bg: "hsl(258 85% 92%)",  fg: "hsl(258 60% 25%)" },  // violet
  security: { bg: "hsl(0 85% 91%)",    fg: "hsl(0 70% 25%)" },    // red
  search:   { bg: "hsl(199 90% 87%)",  fg: "hsl(201 80% 18%)" },  // sky
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
