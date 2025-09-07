import argparse, json, pathlib, re
from typing import List, Dict
from collections import defaultdict
from dotenv import load_dotenv
from openai import OpenAI

# Pricing rates per million tokens (input, output)
RATES = {
    'gpt-5': (1.25, 10.00),
    'gpt-5-mini': (0.25, 2.00),
    'gpt-5-nano': (0.05, 0.40),
    'gpt-4o': (2.50, 10.00),
    'gpt-4o-mini': (0.60, 2.40),
}

DEFAULT_PROMPT = """
ROLE: Quote‑only compiler (OpenAI version).
INPUT: JSONL quotes with fields: page_start, page_end, category, tags, quote.
TASK: Produce two Markdown sections — COMPILATIONS and SNIPPETS.

MANDATES:
- Do NOT paraphrase or invent any body text.
- You MAY add headings and short section notes, but quotes must be verbatim.
- After each quote, append a citation like [p.X–Y].
- Keep outputs deterministic and tidy.
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

def group_key(quote: Dict) -> str:
    """Create a grouping key from category and first tag."""
    cat = quote.get('category', 'untagged')
    tags = quote.get('tags', [])
    lead_tag = tags[0] if tags else 'untagged'
    return f"{cat} × {lead_tag}"

def build_input_block(quotes: List[Dict]) -> str:
    """Build the input block for the prompt from quotes."""
    lines = []
    for q in quotes:
        pstart = q.get('page_start', 0)
        pend = q.get('page_end', 0)
        qt = q.get('quote', '').strip()
        if qt:
            lines.append(f"[p.{pstart}-{pend}] \n{qt}")
    return "\n\n".join(lines)

def split_sections(text: str) -> Dict[str, str]:
    """Extract COMPILATIONS and SNIPPETS sections from response."""
    comp = ""
    snip = ""
    # Try to find fenced blocks first
    m_comp = re.search(r"(?is)\bCOMPILATIONS\b.*?```(.*?)```", text)
    m_snip = re.search(r"(?is)\bSNIPPETS\b.*?```(.*?)```", text)
    if m_comp: comp = m_comp.group(1).strip()
    if m_snip: snip = m_snip.group(1).strip()
    # Fallback: split by headers without fences
    if not comp or not snip:
        parts = re.split(r"(?im)^\s*SNIPPETS\s*$", text, maxsplit=1)
        if len(parts) == 2:
            comp_alt, snip_alt = parts[0], parts[1]
            # Remove leading 'COMPILATIONS' label if present
            comp_alt = re.sub(r"(?im)^\s*COMPILATIONS\s*", "", comp_alt).strip()
            if not comp: comp = comp_alt
            if not snip: snip = snip_alt.strip()
    return { 'compilations': comp.strip(), 'snippets': snip.strip() }

def estimate_tokens(text: str) -> int:
    """Estimate token count using tiktoken if available, fallback to heuristic."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Fallback: rough estimate of 4 chars per token
        return len(text) // 4

def estimate_tokens_and_cost(model: str, groups: Dict[str, List[Dict]], prompt_template: str) -> Dict:
    """Estimate tokens and cost for all groups."""
    total_input_tokens = 0
    total_output_tokens = 0
    
    for key, items in groups.items():
        body = build_input_block(items)
        full_prompt = prompt_template + "\n\nINPUT QUOTES:\n\n" + body
        
        input_tokens = estimate_tokens(full_prompt)
        # Estimate output tokens (roughly 0.3x input for this task)
        output_tokens = int(input_tokens * 0.3)
        
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
    
    # Get pricing rates
    rates = RATES.get(model, (None, None))
    usd_input = None
    usd_output = None
    usd_total = None
    
    if rates[0] is not None and rates[1] is not None:
        usd_input = (total_input_tokens / 1_000_000) * rates[0]
        usd_output = (total_output_tokens / 1_000_000) * rates[1]
        usd_total = usd_input + usd_output
    
    return {
        'input_tokens': total_input_tokens,
        'output_tokens': total_output_tokens,
        'usd_input': usd_input,
        'usd_output': usd_output,
        'usd_total': usd_total,
        'usd_per_million_input': rates[0],
        'usd_per_million_output': rates[1]
    }

def run_compile(model: str, groups: Dict[str, List[Dict]], outdir: pathlib.Path):
    client = OpenAI()
    comp_dir = outdir / 'compilations'
    snip_dir = outdir / 'snippets'
    comp_dir.mkdir(exist_ok=True)
    snip_dir.mkdir(exist_ok=True)

    index_lines = ["# Quote Bundles (GPT)\n"]

    for key, items in groups.items():
        slug = re.sub(r"[^a-z0-9]+","-", key.lower()).strip('-') or 'untagged'
        body = build_input_block(items)
        prompt = DEFAULT_PROMPT + "\n\nINPUT QUOTES:\n\n" + body
        resp = client.responses.create(
            model=model,
            instructions=DEFAULT_PROMPT,
            input=[{"role":"user","content":[{"type":"input_text","text":body}]}],
            temperature=0.2,
        )
        out = resp.output_text
        sections = split_sections(out)
        (comp_dir / f"{slug}.md").write_text(sections.get('compilations','').strip()+"\n", encoding='utf-8')
        (snip_dir / f"{slug}.md").write_text(sections.get('snippets','').strip()+"\n", encoding='utf-8')
        index_lines.append(f"- **{key}** → [compilations/{slug}.md](compilations/{slug}.md), [snippets/{slug}.md](snippets/{slug}.md)")

    (outdir / 'INDEX.md').write_text("\n".join(index_lines)+"\n", encoding='utf-8')

def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument('-i','--input', required=True, help='scan_quotes.jsonl path')
    ap.add_argument('-m','--model', default='gpt-5')
    ap.add_argument('-o','--outdir', required=True)
    ap.add_argument('--estimate-only', action='store_true')
    args = ap.parse_args()

    jsonl = pathlib.Path(args.input)
    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    quotes = load_quotes(jsonl)
    if not quotes:
        raise SystemExit('No quotes found in JSONL.')

    groups: Dict[str, List[Dict]] = defaultdict(list)
    for q in quotes:
        groups[group_key(q)].append(q)

    estimate = estimate_tokens_and_cost(args.model, groups, DEFAULT_PROMPT)

    # Write cost report file
    cost_path = pathlib.Path(args.outdir) / 'cost_report.json'
    if args.estimate_only:
        cost_path.write_text(json.dumps({'estimate': estimate}, indent=2), encoding='utf-8')
        print(json.dumps({'estimate': estimate}, ensure_ascii=False))
        return

    # Write cost report before running
    cost_path.write_text(json.dumps({'estimate': estimate}, indent=2), encoding='utf-8')

    print(f"Estimated input tokens: {estimate['input_tokens']} | output tokens: {estimate['output_tokens']}")
    if estimate['usd_total'] is not None:
        print(f"Estimated cost: ${estimate['usd_total']:.4f} (in ${estimate['usd_input']:.4f} + out ${estimate['usd_output']:.4f})")
    else:
        print("Estimated cost: N/A (no rate for this model)")

    run_compile(args.model, groups, outdir)
    print(f"Wrote grouped outputs → {outdir / 'compilations'} and {outdir / 'snippets'}; index at {outdir / 'INDEX.md'}")

if __name__ == '__main__':
    main()
