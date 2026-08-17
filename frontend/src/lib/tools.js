// Ugh!PDF tool registry (client-side mirror).
export const CATEGORIES = [
  { id: "all", name: "All", color: "#111827", desc: "Every tool in one place" },
  { id: "convert", name: "Convert", color: "#4F46E5", desc: "18 tools to change format" },
  { id: "organize", name: "Organize", color: "#10B981", desc: "5 tools to rearrange pages" },
  { id: "optimize", name: "Optimize", color: "#F59E0B", desc: "5 tools to shrink & fix" },
  { id: "edit", name: "Edit", color: "#8B5CF6", desc: "9 tools to modify content" },
  { id: "security", name: "Security", color: "#EF4444", desc: "8 tools to protect & sign" },
  { id: "ai", name: "AI Studio", color: "#EC4899", desc: "8 AI-powered tools" },
];

// engine: "local" (in browser), "server" (backend), "ai" (AI + backend)
export const TOOLS = [
  // CONVERT (18)
  { id: "pdf-to-word", name: "PDF → Word", cat: "convert", engine: "server", desc: "Editable .docx" },
  { id: "pdf-to-excel", name: "PDF → Excel", cat: "convert", engine: "server", desc: "Tables to .xlsx" },
  { id: "pdf-to-ppt", name: "PDF → PowerPoint", cat: "convert", engine: "server", desc: "Slides from pages" },
  { id: "pdf-to-jpg", name: "PDF → JPG", cat: "convert", engine: "server", desc: "Pages as JPG" },
  { id: "pdf-to-png", name: "PDF → PNG", cat: "convert", engine: "server", desc: "Pages as PNG" },
  { id: "pdf-to-html", name: "PDF → HTML", cat: "convert", engine: "server", desc: "Browsable HTML" },
  { id: "pdf-to-markdown", name: "PDF → Markdown", cat: "convert", engine: "server", desc: "Clean Markdown" },
  { id: "pdf-to-epub", name: "PDF → EPUB", cat: "convert", engine: "server", desc: "eBook ready" },
  { id: "pdf-to-svg", name: "PDF → SVG", cat: "convert", engine: "server", desc: "Vectorized pages" },
  { id: "pdf-to-text", name: "PDF → Text", cat: "convert", engine: "server", desc: "Extract raw text" },
  { id: "word-to-pdf", name: "Word → PDF", cat: "convert", engine: "server", desc: ".docx to PDF" },
  { id: "excel-to-pdf", name: "Excel → PDF", cat: "convert", engine: "server", desc: "Spreadsheet to PDF" },
  { id: "ppt-to-pdf", name: "PowerPoint → PDF", cat: "convert", engine: "server", desc: "Slides to PDF" },
  { id: "jpg-to-pdf", name: "JPG → PDF", cat: "convert", engine: "local", desc: "Images to one PDF" },
  { id: "html-to-pdf", name: "HTML → PDF", cat: "convert", engine: "server", desc: "Web to PDF" },
  { id: "markdown-to-pdf", name: "Markdown → PDF", cat: "convert", engine: "server", desc: "MD to styled PDF" },
  { id: "heic-to-pdf", name: "HEIC → PDF", cat: "convert", engine: "server", desc: "iPhone photos" },
  { id: "svg-to-pdf", name: "SVG → PDF", cat: "convert", engine: "server", desc: "Vectors to PDF" },

  // ORGANIZE (5)
  { id: "merge", name: "Merge PDFs", cat: "organize", engine: "local", desc: "Combine multiple PDFs" },
  { id: "split", name: "Split PDF", cat: "organize", engine: "local", desc: "Pick page ranges" },
  { id: "rotate", name: "Rotate Pages", cat: "organize", engine: "local", desc: "90° / 180° / 270°" },
  { id: "delete-pages", name: "Delete Pages", cat: "organize", engine: "local", desc: "Remove pages" },
  { id: "organize", name: "Reorder Pages", cat: "organize", engine: "local", desc: "Rearrange pages" },

  // OPTIMIZE (5)
  { id: "compress", name: "Compress PDF", cat: "optimize", engine: "local", desc: "Reduce file size" },
  { id: "repair", name: "Repair PDF", cat: "optimize", engine: "server", desc: "Fix corrupt files" },
  { id: "pdfa", name: "PDF/A Archive", cat: "optimize", engine: "server", desc: "Archival grade" },
  { id: "blank-remover", name: "Blank Remover", cat: "optimize", engine: "local", desc: "Skip empty pages" },
  { id: "resize", name: "Resize Pages", cat: "optimize", engine: "local", desc: "A4 / Letter / Legal" },

  // EDIT (9)
  { id: "watermark", name: "Watermark", cat: "edit", engine: "local", desc: "Text watermark" },
  { id: "page-numbers", name: "Page Numbers", cat: "edit", engine: "local", desc: "Number pages" },
  { id: "edit", name: "Edit PDF", cat: "edit", engine: "server", desc: "Text & shapes" },
  { id: "sign", name: "Sign PDF", cat: "edit", engine: "server", desc: "Draw signature" },
  { id: "bates", name: "Bates Numbers", cat: "edit", engine: "server", desc: "Legal stamping" },
  { id: "id-card", name: "ID Card Layout", cat: "edit", engine: "local", desc: "Two IDs / page" },
  { id: "forms", name: "Fill Forms", cat: "edit", engine: "server", desc: "Complete forms" },
  { id: "mobile-reflow", name: "Mobile Reflow", cat: "edit", engine: "server", desc: "Phone friendly" },
  { id: "exif-strip", name: "Strip Metadata", cat: "edit", engine: "local", desc: "Remove EXIF" },

  // SECURITY (8)
  { id: "protect", name: "Password Protect", cat: "security", engine: "server", desc: "Add password" },
  { id: "unlock", name: "Unlock PDF", cat: "security", engine: "server", desc: "Remove password" },
  { id: "flatten", name: "Flatten PDF", cat: "security", engine: "server", desc: "Bake in forms" },
  { id: "redact", name: "Manual Redact", cat: "security", engine: "server", desc: "Black out text" },
  { id: "audit-sign", name: "Audit E-Sign", cat: "security", engine: "server", desc: "SHA-256 stamp" },
  { id: "esign-request", name: "Send for Sign", cat: "security", engine: "server", desc: "Request others" },
  { id: "compare", name: "Compare PDFs", cat: "security", engine: "server", desc: "Pixel diff" },
  { id: "certify", name: "Certify PDF", cat: "security", engine: "server", desc: "Anti-tamper" },

  // AI (8)
  { id: "ai-chat", name: "Chat with PDF", cat: "ai", engine: "ai", credits: 1, desc: "Cited answers" },
  { id: "ai-summarize", name: "Summarize", cat: "ai", engine: "ai", credits: 2, desc: "Structured summary" },
  { id: "ai-redact", name: "AI PII Redactor", cat: "ai", engine: "ai", credits: 3, desc: "Auto-find PII" },
  { id: "ai-extract", name: "Extract Data", cat: "ai", engine: "ai", credits: 3, desc: "Invoices → JSON" },
  { id: "ai-audiobook", name: "Audiobook", cat: "ai", engine: "ai", credits: 5, desc: "Narrated MP3" },
  { id: "ai-visual-diff", name: "Visual Diff", cat: "ai", engine: "ai", credits: 3, desc: "Semantic diff" },
  { id: "ai-math", name: "Homework Solver", cat: "ai", engine: "ai", credits: 2, desc: "Step-by-step" },
  { id: "ai-ocr", name: "Smart OCR", cat: "ai", engine: "ai", credits: 2, desc: "Skips searchable" },
];

export const TOOL_MAP = Object.fromEntries(TOOLS.map((t) => [t.id, t]));
