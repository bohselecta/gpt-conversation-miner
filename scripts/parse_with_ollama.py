import argparse, json, pathlib, subprocess, re
from typing import List, Dict
from collections import defaultdict

DEFAULT_PROMPT = """
ROLE: Quote‑only compiler.
INPUT: A set of JSONL records with exact quotes and metadata.
GOAL: Create:
- compilations.md — themed bundles of quotes grouped by inferred topics
- snippets.md — long, substantial quote sequences worth deeper analysis

STRICT RULES:
- You may NOT paraphrase or invent text.
- You MAY add headings, separators, and section titles of your own.
- All body text under headings must be exact quotes from input.
- Preserve quote order within each snippet when context aids clarity.
- After each quote, include a compact citation like [p.12–14].
OUTPUT FORMAT:
- Return two fenced blocks labeled COMPILATIONS and SNIPPETS, each in Markdown.
""".strip()

def group_key(quote: Dict) -> str:
    """Create a grouping key from category and first tag."""
    cat = quote.get('category', 'untagged')
    tags = quote.get('tags', [])
    lead_tag = tags[0] if tags else 'untagged'
    return f"{cat} × {lead_tag}"

def slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip('-') or 'untagged'

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


def run_ollama(ollama_cmd: str, model: str, prompt: str) -> str:
    # prefer `ollama run MODEL -p PROMPT`
    try:
        res = subprocess.run([ollama_cmd, 'run', model, '-p', prompt], capture_output=True, text=True, check=True)
        return res.stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise SystemExit(f"Failed to run Ollama: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i','--input', required=True, help='scan_quotes.jsonl path')
    ap.add_argument('-m','--model', default='llama3.2')
    ap.add_argument('-o','--outdir', required=True)
    ap.add_argument('-ollama','--ollama', default='ollama')
    args = ap.parse_args()

    jsonl = pathlib.Path(args.input)
    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    quotes = load_quotes(jsonl)
    if not quotes:
        raise SystemExit('No quotes found in JSONL.')

    # Group by category + lead tag for batching
    groups: Dict[str, List[Dict]] = defaultdict(list)
    for q in quotes:
        groups[group_key(q)].append(q)

    comp_dir = outdir / 'compilations'
    snip_dir = outdir / 'snippets'
    comp_dir.mkdir(exist_ok=True)
    snip_dir.mkdir(exist_ok=True)

    index_lines = ["# Quote Bundles\n"]

    for key, items in groups.items():
        slug = slugify(key)
        body = build_input_block(items)
        prompt = DEFAULT_PROMPT + "\n\nINPUT QUOTES:\n\n" + body
        out = run_ollama(args.ollama, args.model, prompt)
        sections = split_sections(out)

        comp_path = comp_dir / f"{slug}.md"
        snip_path = snip_dir / f"{slug}.md"
        comp_path.write_text(sections.get('compilations','').strip() + "\n", encoding='utf-8')
        snip_path.write_text(sections.get('snippets','').strip() + "\n", encoding='utf-8')

        index_lines.append(f"- **{key}** → [compilations/{slug}.md](compilations/{slug}.md), [snippets/{slug}.md](snippets/{slug}.md)")

    (outdir / 'INDEX.md').write_text("\n".join(index_lines) + "\n", encoding='utf-8')
    print(f"Wrote grouped outputs → {comp_dir} and {snip_dir}; index at {outdir / 'INDEX.md'}")

if __name__ == '__main__':
    main()
