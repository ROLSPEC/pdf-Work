"""Registry of all 45 tools in Ugh!PDF grouped by category (AI removed)."""

TOOLS = [
    # ===== CONVERT (18) =====
    {"id": "pdf-to-word", "name": "PDF to Word", "cat": "convert", "engine": "server", "desc": "Convert PDF to editable Word (.docx)"},
    {"id": "pdf-to-excel", "name": "PDF to Excel", "cat": "convert", "engine": "server", "desc": "Extract tables from PDF to Excel"},
    {"id": "pdf-to-ppt", "name": "PDF to PowerPoint", "cat": "convert", "engine": "server", "desc": "Convert PDF pages to PowerPoint slides"},
    {"id": "pdf-to-jpg", "name": "PDF to JPG", "cat": "convert", "engine": "server", "desc": "Extract PDF pages as JPG images"},
    {"id": "pdf-to-png", "name": "PDF to PNG", "cat": "convert", "engine": "server", "desc": "Extract PDF pages as PNG images"},
    {"id": "pdf-to-html", "name": "PDF to HTML", "cat": "convert", "engine": "server", "desc": "Convert PDF to a browsable HTML file"},
    {"id": "pdf-to-markdown", "name": "PDF to Markdown", "cat": "convert", "engine": "server", "desc": "Convert PDF text to clean Markdown"},
    {"id": "pdf-to-epub", "name": "PDF to EPUB", "cat": "convert", "engine": "server", "desc": "Convert PDF to eBook-friendly EPUB"},
    {"id": "pdf-to-svg", "name": "PDF to SVG", "cat": "convert", "engine": "server", "desc": "Convert PDF pages to SVG vectors"},
    {"id": "pdf-to-text", "name": "PDF to Text", "cat": "convert", "engine": "server", "desc": "Extract raw text from PDF"},
    {"id": "word-to-pdf", "name": "Word to PDF", "cat": "convert", "engine": "server", "desc": "Convert .docx to PDF"},
    {"id": "excel-to-pdf", "name": "Excel to PDF", "cat": "convert", "engine": "server", "desc": "Convert Excel to PDF"},
    {"id": "ppt-to-pdf", "name": "PowerPoint to PDF", "cat": "convert", "engine": "server", "desc": "Convert PowerPoint to PDF"},
    {"id": "jpg-to-pdf", "name": "JPG to PDF", "cat": "convert", "engine": "local", "desc": "Combine images into a PDF"},
    {"id": "html-to-pdf", "name": "HTML to PDF", "cat": "convert", "engine": "server", "desc": "Convert web pages to PDF"},
    {"id": "markdown-to-pdf", "name": "Markdown to PDF", "cat": "convert", "engine": "server", "desc": "Convert Markdown to nicely styled PDF"},
    {"id": "heic-to-pdf", "name": "HEIC to PDF", "cat": "convert", "engine": "server", "desc": "iPhone HEIC images to PDF"},
    {"id": "svg-to-pdf", "name": "SVG to PDF", "cat": "convert", "engine": "server", "desc": "SVG vectors to PDF"},

    # ===== ORGANIZE (5) =====
    {"id": "merge", "name": "Merge PDFs", "cat": "organize", "engine": "local", "desc": "Combine multiple PDFs into one"},
    {"id": "split", "name": "Split PDF", "cat": "organize", "engine": "local", "desc": "Split a PDF into separate files"},
    {"id": "rotate", "name": "Rotate Pages", "cat": "organize", "engine": "local", "desc": "Rotate one or all pages"},
    {"id": "delete-pages", "name": "Delete Pages", "cat": "organize", "engine": "local", "desc": "Remove specific pages"},
    {"id": "organize", "name": "Reorder Pages", "cat": "organize", "engine": "local", "desc": "Drag to reorder pages"},

    # ===== OPTIMIZE (5) =====
    {"id": "compress", "name": "Compress PDF", "cat": "optimize", "engine": "local", "desc": "Reduce file size"},
    {"id": "repair", "name": "Repair PDF", "cat": "optimize", "engine": "server", "desc": "Fix corrupted or broken PDFs"},
    {"id": "pdfa", "name": "Convert to PDF/A", "cat": "optimize", "engine": "server", "desc": "Archival-grade PDF/A"},
    {"id": "blank-remover", "name": "Remove Blank Pages", "cat": "optimize", "engine": "local", "desc": "Auto-detect and remove blank pages"},
    {"id": "resize", "name": "Resize Pages", "cat": "optimize", "engine": "local", "desc": "Change page size (A4, Letter, etc.)"},

    # ===== EDIT (9) =====
    {"id": "watermark", "name": "Add Watermark", "cat": "edit", "engine": "local", "desc": "Text or image watermark"},
    {"id": "page-numbers", "name": "Page Numbers", "cat": "edit", "engine": "local", "desc": "Add page numbers"},
    {"id": "edit", "name": "Edit PDF", "cat": "edit", "engine": "server", "desc": "Add text, shapes, annotations"},
    {"id": "sign", "name": "Sign PDF", "cat": "edit", "engine": "server", "desc": "Draw or type a signature"},
    {"id": "bates", "name": "Bates Numbering", "cat": "edit", "engine": "server", "desc": "Legal Bates stamping"},
    {"id": "id-card", "name": "ID Card Layout", "cat": "edit", "engine": "local", "desc": "Two IDs on a single page"},
    {"id": "forms", "name": "Fill Forms", "cat": "edit", "engine": "server", "desc": "Fill in PDF forms"},
    {"id": "mobile-reflow", "name": "Mobile Reflow", "cat": "edit", "engine": "server", "desc": "Reflow for phone screens"},
    {"id": "exif-strip", "name": "Strip Metadata", "cat": "edit", "engine": "local", "desc": "Remove EXIF and metadata"},

    # ===== SECURITY (8) =====
    {"id": "protect", "name": "Password Protect", "cat": "security", "engine": "server", "desc": "Add password to PDF"},
    {"id": "unlock", "name": "Unlock PDF", "cat": "security", "engine": "server", "desc": "Remove password (if you own it)"},
    {"id": "flatten", "name": "Flatten PDF", "cat": "security", "engine": "server", "desc": "Flatten forms + annotations"},
    {"id": "redact", "name": "Manual Redact", "cat": "security", "engine": "server", "desc": "Black out sensitive text"},
    {"id": "audit-sign", "name": "Audit E-Sign", "cat": "security", "engine": "server", "desc": "SHA-256 timestamped signature"},
    {"id": "esign-request", "name": "Send for Signature", "cat": "security", "engine": "server", "desc": "Request e-sign from others"},
    {"id": "compare", "name": "Compare PDFs", "cat": "security", "engine": "server", "desc": "Pixel-level diff of two PDFs"},
    {"id": "certify", "name": "Certify PDF", "cat": "security", "engine": "server", "desc": "Lock PDF against tampering"},

    # ===== SEARCH (1) =====
    {"id": "pdf-search", "name": "Semantic Search", "cat": "search", "engine": "server", "desc": "Find similar text in a PDF (no LLM)"},
]

CATEGORIES = [
    {"id": "convert", "name": "Convert", "desc": "18 tools to change format", "color": "#4F46E5"},
    {"id": "organize", "name": "Organize", "desc": "5 tools to rearrange pages", "color": "#10B981"},
    {"id": "optimize", "name": "Optimize", "desc": "5 tools to shrink & fix", "color": "#F59E0B"},
    {"id": "edit", "name": "Edit", "desc": "9 tools to modify content", "color": "#8B5CF6"},
    {"id": "security", "name": "Security", "desc": "8 tools to protect & sign", "color": "#EF4444"},
    {"id": "search", "name": "Search", "desc": "1 semantic search tool", "color": "#0EA5E9"},
]

TOOL_MAP = {t["id"]: t for t in TOOLS}
