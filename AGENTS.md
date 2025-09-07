# OpenAI Research Scanner — Agent Plan

## Agent A: PDF/JSON Sweeper (OpenAI)
- input: pdf path or conversations.json
- task: chunk pages/conversations, extract **direct quotes** that signal ideas / white‑paper seeds / research directions.
- output: JSON object per chunk, consolidated into JSONL rows: {page_start, page_end, quote, category, tags}
- guardrails: response_format=json_object, temperature=0.1, post‑verification against chunk text

## Agent B: Quote‑Only Compiler (OpenAI/Ollama)
- input: JSONL quotes
- task: batch by (category × lead tag); for each group, stitch **quote‑only** compilations/snippets (no paraphrase; headings allowed)
- output: Markdown bundles per group → `/output/<run>/compilations/*.md` and `/output/<run>/snippets/*.md`; plus `INDEX.md`

## Agent C: Apps & Tools Reconstructor (OpenAI)
- input: JSONL quotes (prefers category=app_tool; also scans ideas/directions with tool-like hints)
- task: infer distinct apps/tools; generate titles and 1–2 sentence summaries; classify status; link page evidence
- output: `/output/<run>/apps_tools/apps_and_tools.json` and `apps_and_tools.md`
