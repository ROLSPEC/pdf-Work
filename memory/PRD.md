# Ugh!PDF — PRD

## Problem statement (original)
PDF Suite — 53 tools (6 categories: Convert 18, Organize 5, Optimize 5, Edit 9, Security 8, AI 8), hybrid processing (in-browser via pdf-lib + server via pikepdf/pypdf), $1 lifetime unlock, streaming AI (chat/summary/PII/extract/audiobook/math/diff/OCR).

## Personas
- Students/freelancers hitting iLovePDF/Smallpdf paywalls
- Legal/ops needing redaction, Bates, audit e-sign
- Anyone wanting Chat-with-PDF without ChatGPT Plus

## Static requirements
- JWT + Emergent Google OAuth auth
- Stripe payments ($1 lifetime, geo-priced; mock fallback in dev)
- Emergent Universal LLM Key (Gemini 2.5 Flash + GPT-4o Mini)
- MongoDB (users, credits, ops counters)
- Free: 25MB, 10 ops/day, 5 AI credits/mo. Paid: 100MB, 200 ops/day, 50 credits/mo
- BYOK (OpenAI/Gemini) for overflow

## Implemented (v1 — 2026-02-13)
- 53-tool registry + 6-category landing grid + universal drop-zone with smart suggestions
- Neo-Brutalist UI (Archivo Black + Space Grotesk + JetBrains Mono; lime primary, coral accent; hard offset shadows, 2px borders)
- Auth: email/password JWT signup+login+/me + Emergent Google OAuth callback
- 12 in-browser tools with pdf-lib: merge, split, rotate, delete pages, reorder, watermark, page numbers, compress, jpg→pdf, id-card, blank-remover, resize, exif-strip
- Server tools: protect (pikepdf), unlock, flatten, repair, pdf-to-text, pdf-to-markdown, bates numbering, exif strip
- AI tools (Emergent LLM): ai-chat, ai-summarize, ai-extract (JSON), ai-redact (regex+Luhn+LLM), ai-math, ai-ocr (auto-detect), ai-visual-diff, ai-audiobook (text chapters, MP3 stub)
- Credit engine: per-tool credit cost, monthly reset, ops/day enforcement, 402 on out-of-credits, 429 on daily cap
- Stripe checkout + mock unlock fallback
- Dashboard: plan/credits/ops stats + BYOK keys management
- Pricing page with tilt-brutalist $1 card
- Light + dark mode toggle

## Test results
- Backend: 35/35 pytest passed (auth, all server tools, all AI tools, credits, BYOK, billing mock, google-invalid)
- One fix mid-flight: pdf_ops.repair removed invalid `allow_overwriting_input=True` for BytesIO input
- ai_service dotenv load-order bug fixed (load .env before import)

## Backlog / P1
- Real Stripe production keys (currently mock unlock when STRIPE_SECRET_KEY absent)
- Real TTS audiobook via OpenAI Audio Speech (only chapter text now)
- Server conversions using LibreOffice/Pandoc (Word/Excel/PPT/EPUB) — currently `run-generic` echoes file
- OCR via Tesseract for scanned pages (only detection now)
- Streaming SSE for chat responses (currently returns full text)
- Cloudflare Turnstile on signup/upload
- Object Storage (S3) upload with 1h TTL for large files (currently in-memory)
- ClamAV virus scan on upload
- Referral system (give $1, get 20 credits)
- Razorpay for India
- File-size booster ($0.25 for 200MB / 24h)

## P2
- Chrome extension, desktop app
- Team accounts / shared workspaces
- Batch/folder processing
- Full eIDAS qualified e-sign
- i18n
