import { Link } from "react-router-dom";
import { Sparkle, Lock, Cloud } from "@phosphor-icons/react";

const CAT_BG = {
  convert: "bg-sky/40",
  organize: "bg-primary/40",
  optimize: "bg-sun/40",
  edit: "bg-grape/40",
  security: "bg-accent/30",
  ai: "bg-accent",
};
const CAT_TEXT = {
  ai: "text-accent-foreground",
};

export default function ToolCard({ tool }) {
  const bg = CAT_BG[tool.cat] || "bg-card";
  const text = CAT_TEXT[tool.cat] || "text-foreground";
  return (
    <Link
      to={`/t/${tool.id}`}
      data-testid={`tool-${tool.id}`}
      className={`group brut brut-hover relative flex flex-col justify-between p-4 h-36 ${bg} ${text}`}
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
        {tool.engine === "ai" ? (
          <span>{tool.credits} credit{tool.credits > 1 ? "s" : ""}</span>
        ) : (
          <span>{tool.engine === "local" ? "🔒 local" : "☁ cloud"}</span>
        )}
        <span className="opacity-0 group-hover:opacity-100 transition-opacity">→ open</span>
      </div>
    </Link>
  );
}
