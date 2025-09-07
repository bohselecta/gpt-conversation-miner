import os, json, argparse, math, pathlib, re, unicodedata
from typing import List, Dict
import pdfplumber
from tqdm import tqdm
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

class Quote(BaseModel):
    page_start: int
    page_end: int
    category: str
    tags: List[str]
    quote: str

SCAN_SYS_PROMPT = (pathlib.Path('prompts/scan_system.txt').read_text(encoding='utf-8')
                   if pathlib.Path('prompts/scan_system.txt').exists() else
                   "You are a quote extractor. Output JSONL: {page_start,page_end,category,tags,quote}")

CHARS_PER_CHUNK = 9000  # broad sweep to control token cost


def chunk_pages(pages: List[str], chars_per_chunk=CHARS_PER_CHUNK):
    chunks = []
    buf, start_page = "", 1
    for i, text in enumerate(pages, start=1):
        if len(buf) + len(text) > chars_per_chunk and buf:
            chunks.append((start_page, i-1, buf))
            buf, start_page = "", i
        buf += f"\n\n[p.{i}]\n" + text
    if buf:
        chunks.append((start_page, len(pages), buf))
    return chunks


def normalize_text(text: str) -> str:
    """Normalize text for comparison by removing extra whitespace and unicode variations."""
    if not text:
        return ""
    # Normalize unicode, remove extra whitespace, convert to lowercase
    normalized = unicodedata.normalize('NFKD', text)
    normalized = re.sub(r'\s+', ' ', normalized.strip().lower())
    return normalized

def extract_quotes(client: OpenAI, model: str, chunk_text: str, p_start: int, p_end: int) -> List[Dict]:
    instr = SCAN_SYS_PROMPT + f"\nChunk pages: {p_start}-{p_end}. Return JSON object only."
    resp = client.responses.create(
        model=model,
        instructions=instr,
        input=[{"role":"user","content":[{"type":"input_text","text":chunk_text}]}],
        # Keep it terse for cost
        temperature=0.1,
        response_format={"type": "json_object"}
    )
    txt = resp.output_text
    records = []
    
    try:
        # Try to parse as single JSON object first
        obj = json.loads(txt)
        if 'quotes' in obj and isinstance(obj['quotes'], list):
            for quote_data in obj['quotes']:
                try:
                    q = Quote(**quote_data)
                    records.append(q.model_dump())
                except Exception:
                    pass
    except Exception:
        # fallback: try line-by-line JSON if model deviates
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                try:
                    q = Quote(**json.loads(line)).model_dump()
                    records.append(q)
                except Exception:
                    pass

    # Quote verification against the actual chunk to eliminate drift
    norm_chunk = normalize_text(chunk_text)
    verified = []
    for r in records:
        qnorm = normalize_text(r['quote'])
        if qnorm and qnorm in norm_chunk:
            # Clamp page range to this chunk's declared bounds
            r['page_start'] = max(p_start, int(r['page_start']))
            r['page_end'] = min(p_end, int(r['page_end']))
            verified.append(r)
    return verified


def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument('-i','--input', required=True, help='PDF file path')
    ap.add_argument('-o','--outdir', required=True, help='Output directory')
    ap.add_argument('-m','--model', default=os.getenv('OPENAI_MODEL','gpt-5'))
    args = ap.parse_args()

    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise SystemExit('OPENAI_API_KEY is not set. Provide via GUI or .env')

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    jsonl_path = outdir / 'scan_quotes.jsonl'

    with pdfplumber.open(args.input) as pdf:
        pages_text = [ (p.extract_text() or '') for p in pdf.pages ]

    chunks = chunk_pages(pages_text)
    client = OpenAI()

    kept_total = 0
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for p_start, p_end, text in tqdm(chunks, desc='Scanning'):
            recs = extract_quotes(client, args.model, text, p_start, p_end)
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
            kept_total += len(recs)

    print(f"Wrote {kept_total} verified quotes → {jsonl_path}")

if __name__ == '__main__':
    main()
