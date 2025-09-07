# Glyphd Research Scanner — Agent Plan

## Agent A: PDF Sweeper (OpenAI)
- input: pdf path
- task: chunk pages, extract **direct quotes** that signal ideas / white‑paper seeds / research directions.
- output: JSON object per chunk, consolidated into JSONL rows: {page_start, page_end, quote, category, tags}
- guardrails: response_format=json_object, temperature=0.1, seed=42, post‑verification against chunk text

## Agent B: Quote‑Only Compiler (Ollama)
- input: JSONL quotes
- task: batch by (category × lead tag); for each group, stitch **quote‑only** compilations/snippets (no paraphrase; headings allowed)
- output: Markdown bundles per group → `/output/<run>/compilations/*.md` and `/output/<run>/snippets/*.md`; plus `INDEX.md`
