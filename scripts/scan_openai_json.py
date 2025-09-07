import os, json, argparse, pathlib, re, unicodedata
from typing import List, Dict
from tqdm import tqdm
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

CHARS_PER_CHUNK = 9000
PSEUDO_PAGE_SIZE = 2500  # split long convs into page-sized slices

class Quote(BaseModel):
    page_start: int
    page_end: int
    category: str
    tags: List[str]
    quote: str

SCAN_SYS_PROMPT = (pathlib.Path('prompts/scan_system.txt').read_text(encoding='utf-8')
                   if pathlib.Path('prompts/scan_system.txt').exists() else
                   "Return a JSON object with key 'quotes' -> array of {page_start,page_end,category,tags,quote}.")

def normalize_text(s: str) -> str:
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

# ----- Input loading -----

def _extract_message_text(msg: Dict) -> str:
    if not isinstance(msg, dict):
        return ''
    cont = msg.get('content')

    # common export shapes
    if isinstance(cont, dict):
        parts = cont.get('parts')
        if isinstance(parts, list):
            return "\n".join(p for p in parts if isinstance(p, str))
        txt = cont.get('text')
        if isinstance(txt, str):
            return txt
        if isinstance(txt, list):
            return "\n".join([t.get('value') or t.get('text') or '' for t in txt if isinstance(t, dict)])

    if isinstance(cont, list):
        buf = []
        for it in cont:
            if isinstance(it, str):
                buf.append(it)
            elif isinstance(it, dict):
                t = it.get('text') or it.get('value') or ''
                if isinstance(t, str):
                    buf.append(t)
        if buf:
            return "\n".join(buf)

    if isinstance(msg.get('text'), str):
        return msg['text']

    parts = msg.get('parts')
    if isinstance(parts, list):
        return "\n".join(p for p in parts if isinstance(p, str))

    return ''

def load_pages_from_openai_json(path: str) -> List[str]:
    p = pathlib.Path(path)
    data = json.loads(p.read_text(encoding='utf-8'))
    convs = data if isinstance(data, list) else data.get('conversations') or []
    pages: List[str] = []

    for idx, conv in enumerate(convs, start=1):
        title = conv.get('title') or f'Conversation {idx}'
        texts: List[str] = []

        # Prefer mapping graph if present
        mapping = conv.get('mapping')
        if isinstance(mapping, dict) and mapping:
            nodes = list(mapping.values())
            def node_time(n):
                m = n.get('message') or {}
                return m.get('create_time') or 0
            nodes.sort(key=node_time)
            for n in nodes:
                m = n.get('message') or {}
                t = _extract_message_text(m)
                if t:
                    role = ((m.get('author') or {}).get('role') or 'unknown').upper()
                    texts.append(f"{role}: {t}")

        # Fallback to flat messages
        if not texts and isinstance(conv.get('messages'), list):
            for m in conv['messages']:
                t = _extract_message_text(m)
                if t:
                    role = (m.get('role') or 'unknown').upper()
                    texts.append(f"{role}: {t}")

        if not texts:
            continue

        header = f"[CONV: {title}]\n"
        full = header + "\n\n".join(texts)

        # Split into pseudo-pages so downstream shows [p.X] refs
        for off in range(0, len(full), PSEUDO_PAGE_SIZE):
            pages.append(full[off:off+PSEUDO_PAGE_SIZE])

    return pages

# ----- Chunking -----

def chunk_pages(pages: List[str], chars_per_chunk=CHARS_PER_CHUNK):
    chunks = []
    buf, start_page = "", 1
    for i, text in enumerate(pages, start=1):
        text = text or ''
        if len(buf) + len(text) > chars_per_chunk and buf:
            chunks.append((start_page, i-1, buf))
            buf, start_page = "", i
        buf += f"\n\n[p.{i}]\n" + text
    if buf:
        chunks.append((start_page, len(pages), buf))
    return chunks

# ----- OpenAI call -----

def extract_quotes(client: OpenAI, model: str, chunk_text: str, p_start: int, p_end: int) -> List[Dict]:
    instr = SCAN_SYS_PROMPT + f"\nChunk pages: {p_start}-{p_end}. Output ONLY the JSON object."
    resp = client.responses.create(
        model=model,
        instructions=instr,
        input=[{"role":"user","content":[{"type":"input_text","text":chunk_text}]}],
        temperature=0.1,
    )
    txt = resp.output_text
    records = []
    try:
        obj = json.loads(txt)
        for item in obj.get('quotes', []):
            try:
                q = Quote(**item).model_dump()
                records.append(q)
            except Exception:
                continue
    except Exception:
        # loose fallback
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                try:
                    q = Quote(**json.loads(line)).model_dump()
                    records.append(q)
                except Exception:
                    pass

    # Verify each quote is verbatim in the chunk (no hallucinations)
    norm_chunk = normalize_text(chunk_text)
    verified = []
    for r in records:
        qnorm = normalize_text(r['quote'])
        if qnorm and qnorm in norm_chunk:
            r['page_start'] = max(p_start, int(r['page_start']))
            r['page_end'] = min(p_end, int(r['page_end']))
            verified.append(r)
    return verified

def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument('-i','--input', required=True, help='OpenAI conversations.json path')
    ap.add_argument('-o','--outdir', required=True, help='Output directory')
    ap.add_argument('-m','--model', default=os.getenv('OPENAI_MODEL','gpt-5'))
    args = ap.parse_args()

    if not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('OPENAI_API_KEY is not set. Provide via GUI or .env')

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    jsonl_path = outdir / 'scan_quotes.jsonl'

    pages = load_pages_from_openai_json(args.input)
    chunks = chunk_pages(pages)
    client = OpenAI()

    kept_total = 0
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for p_start, p_end, text in tqdm(chunks, desc='Scanning JSON'):
            recs = extract_quotes(client, args.model, text, p_start, p_end)
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
            kept_total += len(recs)

    print(f"Wrote {kept_total} verified quotes → {jsonl_path}")

if __name__ == '__main__':
    main()
