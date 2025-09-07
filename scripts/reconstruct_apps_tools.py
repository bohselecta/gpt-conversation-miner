#!/usr/bin/env python3
"""Reconstruct apps and tools from quotes with deduplication."""

import argparse, json, pathlib, re, difflib
from typing import List, Dict
from dotenv import load_dotenv
from openai import OpenAI

DEFAULT_PROMPT = """
ROLE: Product reconstructor.
OBJECTIVE: From the quoted evidence below, infer distinct apps/tools that the author conceived, started, or partially built. DO NOT invent capabilities not suggested by the quotes.

OUTPUT (JSON ONLY):
Return exactly one JSON object with key "apps" mapping to an array of objects. Each object must include:
- title: short, generated (<= 6 words)
- summary: 1–2 sentences grounded in the quotes (no fabrication)
- status: one of {idea, prototype, partial, built, unknown}
- evidence_pages: array of page numbers referenced across the quotes
- names_detected: array of proper names/brands mentioned in the evidence (e.g., Glyph Drive, TGO, CrashRewind)
- evidence_quotes: array of 1–3 representative quotes (verbatim)

Rules:
- You MAY rephrase for title/summary, but keep them faithful to evidence.
- Prefer merging near-duplicates into one item.
- If evidence is thin, mark status "unknown".
""".strip()

def load_quotes(jsonl_path: pathlib.Path) -> List[dict]:
    quotes = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                quotes.append(json.loads(line))
            except Exception:
                pass
    return quotes

def merge_similar_apps(apps, thresh=0.85):
    """Merge apps with similar titles using fuzzy matching."""
    merged = []
    for app in apps:
        title = (app.get('title') or '').strip()
        if not title:
            merged.append(app)
            continue
        norm = re.sub(r'[^a-z0-9 ]+','', title.lower())
        found = False
        for m in merged:
            mtitle = (m.get('title') or '')
            mnorm = re.sub(r'[^a-z0-9 ]+','', mtitle.lower())
            if difflib.SequenceMatcher(None, norm, mnorm).ratio() >= thresh:
                # merge evidence fields
                for k in ('evidence_pages','evidence_quotes','names_detected'):
                    m[k] = sorted(set((m.get(k) or []) + (app.get(k) or [])))
                found = True
                break
        if not found:
            merged.append(app)
    return merged

def run_apps_tools(model: str, quotes: List[Dict], outdir: pathlib.Path):
    """Run apps & tools reconstruction."""
    client = OpenAI()
    
    # Build input from quotes
    input_text = "\n\n".join([
        f"[p.{q.get('page_start', 0)}-{q.get('page_end', 0)}] {q.get('quote', '')}"
        for q in quotes
    ])
    
    prompt = DEFAULT_PROMPT + "\n\nEVIDENCE:\n\n" + input_text
    
    resp = client.responses.create(
        model=model,
        instructions=DEFAULT_PROMPT,
        input=[{"role":"user","content":[{"type":"input_text","text":input_text}]}],
        temperature=0.2,
    )
    
    out = resp.output_text
    
    # Parse JSON response
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', out, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            raise ValueError("Could not parse JSON from response")
    
    # Deduplicate apps
    data['apps'] = merge_similar_apps(data.get('apps', []))
    
    # Write outputs
    apps_dir = outdir / 'apps_tools'
    apps_dir.mkdir(exist_ok=True)
    
    json_path = apps_dir / 'apps_and_tools.json'
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    
    # Generate markdown summary
    md_lines = ["# Apps & Tools Reconstruction\n"]
    for app in data.get('apps', []):
        title = app.get('title', 'Untitled')
        summary = app.get('summary', 'No summary available')
        status = app.get('status', 'unknown')
        pages = app.get('evidence_pages', [])
        
        md_lines.append(f"## {title}")
        md_lines.append(f"**Status:** {status}")
        md_lines.append(f"**Pages:** {', '.join(map(str, pages))}")
        md_lines.append(f"**Summary:** {summary}")
        
        if app.get('names_detected'):
            md_lines.append(f"**Names detected:** {', '.join(app['names_detected'])}")
        
        if app.get('evidence_quotes'):
            md_lines.append("**Evidence quotes:**")
            for quote in app['evidence_quotes']:
                md_lines.append(f"- {quote}")
        
        md_lines.append("")
    
    md_path = apps_dir / 'apps_and_tools.md'
    md_path.write_text("\n".join(md_lines), encoding='utf-8')
    
    print(f"Wrote apps & tools → {json_path}")
    print(f"Wrote markdown → {md_path}")

def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument('-i','--input', required=True, help='scan_quotes.jsonl path')
    ap.add_argument('-m','--model', default='gpt-5')
    ap.add_argument('-o','--outdir', required=True)
    args = ap.parse_args()

    if not pathlib.Path(args.input).exists():
        raise SystemExit(f"Input file not found: {args.input}")

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    quotes = load_quotes(pathlib.Path(args.input))
    if not quotes:
        raise SystemExit('No quotes found in JSONL.')

    run_apps_tools(args.model, quotes, outdir)

if __name__ == '__main__':
    main()
