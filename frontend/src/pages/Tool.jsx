import { useEffect, useState } from "react";
import { useNavigate, useLocation, useParams, Link } from "react-router-dom";
import { TOOL_MAP } from "@/lib/tools";
import * as pdfOps from "@/lib/pdfOps";
import { API } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import DropZone from "@/components/DropZone";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { ArrowLeft, Lock, Cloud, Download, WarningCircle } from "@phosphor-icons/react";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";

export default function ToolPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { state } = useLocation();
  const { user, refresh } = useAuth();
  const tool = TOOL_MAP[id];
  const [files, setFiles] = useState(state?.file ? [state.file] : []);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [opts, setOpts] = useState({});

  useEffect(() => {
    setFiles(state?.file ? [state.file] : []);
    setResult(null); setError(null); setProgress(0); setOpts({});
  }, [id, state]);

  if (!tool) return <div className="p-10 text-center font-display text-2xl">Tool not found. <Link to="/" className="underline">Go home</Link></div>;

  const needsAuth = tool.engine !== "local";
  const needsMulti = tool.id === "merge" || tool.id === "jpg-to-pdf" || tool.id === "id-card";

  const requireAuth = () => {
    if (!user && needsAuth) { toast.error("Please log in to use cloud tools."); nav("/login"); return false; }
    return true;
  };

  const runLocal = async () => {
    setBusy(true); setError(null); setProgress(20);
    try {
      const t = tool.id;
      if (t === "merge") await pdfOps.merge(files);
      else if (t === "split") await pdfOps.split(files[0], parseRanges(opts.ranges || "1-1"));
      else if (t === "rotate") await pdfOps.rotate(files[0], parseInt(opts.angle || "90", 10));
      else if (t === "delete-pages") await pdfOps.deletePages(files[0], parsePages(opts.pages || ""));
      else if (t === "organize") await pdfOps.reorder(files[0], parsePages(opts.order || ""));
      else if (t === "watermark") await pdfOps.watermark(files[0], opts.text || "CONFIDENTIAL");
      else if (t === "page-numbers") await pdfOps.pageNumbers(files[0], opts.position || "bottom-right");
      else if (t === "compress") await pdfOps.compress(files[0]);
      else if (t === "jpg-to-pdf") await pdfOps.jpgsToPdf(files);
      else if (t === "id-card") await pdfOps.idCardLayout(files);
      else if (t === "blank-remover") await pdfOps.blankRemover(files[0]);
      else if (t === "resize") await pdfOps.resize(files[0], opts.size || "A4");
      else if (t === "exif-strip") await pdfOps.stripMetadata(files[0]);
      setProgress(100);
      setResult({ kind: "download", msg: "Saved to your downloads folder." });
      toast.success("Done!");
    } catch (e) {
      setError(e.message || "Something went wrong");
      toast.error("Failed: " + (e.message || "unknown"));
    } finally { setBusy(false); }
  };

  const runServer = async () => {
    if (!requireAuth()) return;
    setBusy(true); setError(null); setProgress(15); setResult(null);
    try {
      const fd = new FormData();
      fd.append("file", files[0]);
      Object.entries(opts).forEach(([k, v]) => v != null && fd.append(k, v));
      const endpoint = pickEndpoint(tool);
      setProgress(45);
      const resp = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${localStorage.getItem("ughpdf_token") || ""}` },
        body: fd,
      });
      setProgress(80);
      if (!resp.ok) {
        const t = await resp.text();
        let msg = t; try { msg = JSON.parse(t).detail || msg; } catch { }
        throw new Error(msg || `HTTP ${resp.status}`);
      }
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      setResult({ kind: "file", url, name: `${tool.id}-${files[0].name}` });
      setProgress(100);
      toast.success("Done!");
      refresh();
    } catch (e) {
      setError(e.message || "Failed");
      toast.error(e.message || "Failed");
    } finally { setBusy(false); }
  };

  const canRun = files.length > 0 && (!needsMulti || files.length >= 2) && !busy;

  const engineBadge = (
    <span className="brut-chip bg-card">
      {tool.engine === "local"
        ? <><Lock size={11} weight="bold" /> Local · Private</>
        : <><Cloud size={11} weight="bold" /> Cloud · deleted in 24h</>}
    </span>
  );

  return (
    <div className="max-w-6xl mx-auto px-6 py-10">
      <button onClick={() => nav("/")} className="text-xs font-mono uppercase tracking-widest font-bold flex items-center gap-1 mb-6 hover:underline" data-testid="back-btn">
        <ArrowLeft size={14} weight="bold" /> All tools
      </button>

      <div className="brut p-6 mb-6 bg-card">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="brut-chip mb-3" data-testid="tool-cat-chip">{tool.cat}</div>
            <h1 className="font-display text-4xl sm:text-5xl tracking-tighter" data-testid="tool-title">{tool.name}</h1>
            <p className="text-sm mt-2 font-medium">{tool.desc}</p>
          </div>
          <div>{engineBadge}</div>
        </div>
      </div>

      <div className="grid md:grid-cols-[1fr_320px] gap-6">
        <div className="space-y-4">
          {files.length === 0 ? (
            <DropZone
              multiple={needsMulti}
              accept={tool.id === "jpg-to-pdf" || tool.id === "id-card" ? { "image/*": [".jpg", ".jpeg", ".png", ".heic"] } : { "application/pdf": [".pdf"] }}
              hint={`${needsMulti ? "Two+ files" : "One PDF"} · up to ${user?.plan === "lifetime" ? 100 : 25}MB`}
              onFiles={(fs) => setFiles(needsMulti ? fs : [fs[0]])}
              testId="tool-dropzone"
            />
          ) : (
            <div className="brut-sm bg-card p-4">
              <div className="text-[10px] font-mono uppercase tracking-widest font-bold mb-2">↳ Files ({files.length})</div>
              <ul className="space-y-2">
                {files.map((f, i) => (
                  <li key={i} className="flex items-center justify-between text-sm border-b-2 border-border pb-2 last:border-b-0">
                    <span className="truncate font-medium">{f.name}</span>
                    <span className="font-mono text-xs">{(f.size / 1024 / 1024).toFixed(2)}MB</span>
                  </li>
                ))}
              </ul>
              <button onClick={() => setFiles([])} className="mt-3 text-xs font-mono uppercase tracking-widest font-bold hover:underline" data-testid="clear-files">× Clear</button>
            </div>
          )}

          <ToolConfig tool={tool} opts={opts} setOpts={setOpts} />

          {busy && (
            <div className="brut-sm bg-card p-4">
              <Progress value={progress} className="h-3 rounded-none" />
              <p className="text-xs font-mono uppercase tracking-widest mt-3">Working… {progress}%</p>
            </div>
          )}
          {error && (
            <div className="brut bg-destructive/10 border-destructive p-4 flex gap-2 text-destructive font-medium" data-testid="tool-error">
              <WarningCircle size={18} weight="bold" /> {error}
            </div>
          )}
          {result && (
            <div className="brut bg-primary/20 p-5" data-testid="tool-result">
              <div className="brut-chip bg-card mb-3">✓ result</div>
              {result.kind === "download" && <p className="font-medium">{result.msg}</p>}
              {result.kind === "file" && (
                <a href={result.url} download={result.name} className="inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest font-bold brut-sm btn-ink px-4 py-2 brut-hover">
                  <Download size={14} weight="bold" /> Download {result.name}
                </a>
              )}
            </div>
          )}
        </div>

        <aside className="space-y-4">
          <div className="brut bg-card p-5">
            <div className="text-[10px] font-mono uppercase tracking-widest font-bold mb-3">↳ Action</div>
            <button
              disabled={!canRun}
              onClick={() => (tool.engine === "local" ? runLocal() : runServer())}
              data-testid="tool-run"
              className="w-full brut-sm brut-hover btn-primary-ink font-mono text-xs uppercase tracking-widest font-bold py-3 flex items-center justify-center gap-2 disabled:opacity-40 disabled:pointer-events-none"
            >
              {busy ? "Working…" : `Run ${tool.name}`}
            </button>
            {tool.engine === "server" && !user && (
              <p className="text-xs mt-3 font-medium">Log in to use cloud tools.</p>
            )}
          </div>
          <div className="brut bg-primary/40 p-5">
            <div className="text-[10px] font-mono uppercase tracking-widest font-bold mb-2">↳ How it works</div>
            <ol className="text-sm font-medium space-y-1.5 list-decimal list-inside">
              <li>Drop your file</li>
              <li>Configure options</li>
              <li>Click Run</li>
              <li>Preview & download</li>
            </ol>
          </div>
        </aside>
      </div>
    </div>
  );
}

function parseRanges(s) { return s.split(",").map((p) => { const [a, b] = p.split("-").map((x) => parseInt(x.trim(), 10)); return [a || 1, b || a || 1]; }); }
function parsePages(s) { return s.split(",").map((x) => parseInt(x.trim(), 10)).filter(Boolean); }
function pickEndpoint(tool) {
  const direct = new Set(["protect", "unlock", "flatten", "repair", "pdf-to-text", "pdf-to-markdown", "bates"]);
  return direct.has(tool.id) ? `/tools/${tool.id}/run` : `/tools/${tool.id}/run-generic`;
}

function ToolConfig({ tool, opts, setOpts }) {
  const set = (k, v) => setOpts((o) => ({ ...o, [k]: v }));
  const inputCls = "rounded-none border-2 border-border font-mono";
  const wrap = (label, node) => (
    <div className="brut-sm bg-card p-4">
      <Label className="text-[10px] font-mono uppercase tracking-widest font-bold">{label}</Label>
      <div className="mt-2">{node}</div>
    </div>
  );
  if (tool.id === "split") return wrap("Page ranges (e.g. 1-3, 5-7)",
    <Input value={opts.ranges || ""} onChange={(e) => set("ranges", e.target.value)} placeholder="1-3, 5-7" className={inputCls} data-testid="opt-ranges" />);
  if (tool.id === "rotate") return wrap("Rotation angle",
    <Select value={opts.angle || "90"} onValueChange={(v) => set("angle", v)}>
      <SelectTrigger className={inputCls} data-testid="opt-angle"><SelectValue /></SelectTrigger>
      <SelectContent><SelectItem value="90">90°</SelectItem><SelectItem value="180">180°</SelectItem><SelectItem value="270">270°</SelectItem></SelectContent>
    </Select>);
  if (tool.id === "delete-pages") return wrap("Pages to delete (e.g. 2,4,6)",
    <Input value={opts.pages || ""} onChange={(e) => set("pages", e.target.value)} className={inputCls} data-testid="opt-pages" />);
  if (tool.id === "organize") return wrap("New order (e.g. 3,1,2,4)",
    <Input value={opts.order || ""} onChange={(e) => set("order", e.target.value)} className={inputCls} data-testid="opt-order" />);
  if (tool.id === "watermark") return wrap("Watermark text",
    <Input value={opts.text || ""} placeholder="CONFIDENTIAL" onChange={(e) => set("text", e.target.value)} className={inputCls} data-testid="opt-watermark" />);
  if (tool.id === "page-numbers") return wrap("Position",
    <Select value={opts.position || "bottom-right"} onValueChange={(v) => set("position", v)}>
      <SelectTrigger className={inputCls} data-testid="opt-position"><SelectValue /></SelectTrigger>
      <SelectContent><SelectItem value="bottom-right">Bottom right</SelectItem><SelectItem value="bottom-left">Bottom left</SelectItem></SelectContent>
    </Select>);
  if (tool.id === "resize") return wrap("Target size",
    <Select value={opts.size || "A4"} onValueChange={(v) => set("size", v)}>
      <SelectTrigger className={inputCls} data-testid="opt-size"><SelectValue /></SelectTrigger>
      <SelectContent><SelectItem value="A4">A4</SelectItem><SelectItem value="Letter">Letter</SelectItem><SelectItem value="Legal">Legal</SelectItem></SelectContent>
    </Select>);
  if (tool.id === "protect" || tool.id === "unlock") return wrap("Password",
    <Input type="password" value={opts.password || ""} onChange={(e) => set("password", e.target.value)} className={inputCls} data-testid="opt-password" />);
  if (tool.id === "bates") return (
    <div className="grid grid-cols-2 gap-3">
      {wrap("Prefix", <Input value={opts.prefix || ""} placeholder="BATES" onChange={(e) => set("prefix", e.target.value)} className={inputCls} data-testid="opt-prefix" />)}
      {wrap("Start #", <Input type="number" value={opts.start || ""} placeholder="1" onChange={(e) => set("start", e.target.value)} className={inputCls} data-testid="opt-start" />)}
    </div>
  );
  return null;
}
