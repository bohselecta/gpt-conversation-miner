import os, json, argparse, pathlib, re, unicodedata, glob, csv
from typing import List, Dict
from tqdm import tqdm
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# Try to import ijson for streaming
try:
    import ijson
except ImportError:
    ijson = None

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

def norm_key(s: str) -> str:
    """Create normalized key for deduplication."""
    return re.sub(r'\s+', ' ', normalize_text(s)).lower()

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

def stream_conversations(fp):
    """Stream conversations from file, trying ijson first, fallback to json."""
    if ijson is None:
        data = json.load(fp)
        return data if isinstance(data, list) else data.get('conversations', [])
    # Try both top-level shapes
    try:
        return ijson.items(fp, 'item')  # list at top
    except Exception:
        fp.seek(0)
        return ijson.items(fp, 'conversations.item')

def iter_inputs(path: str):
    """Iterate over input files - single file or directory."""
    if os.path.isdir(path):
        for fn in glob.glob(os.path.join(path, '*.json')):
            if not fn.endswith('index.html'):  # Skip index files
                yield fn
    else:
        yield path

def load_pages_from_openai_json_one(path: str, include_user=True, include_assistant=True) -> List[str]:
    """Load pages from a single JSON file with role filtering."""
    pages = []
    with open(path, 'r', encoding='utf-8') as fp:
        for conv in stream_conversations(fp):
            title = conv.get('title') or 'Conversation'
            texts = []
            mapping = conv.get('mapping')
            if isinstance(mapping, dict) and mapping:
                nodes = sorted(mapping.values(), key=lambda n: (n.get('message') or {}).get('create_time') or 0)
                for n in nodes:
                    m = n.get('message') or {}
                    role = ((m.get('author') or {}).get('role') or 'unknown').lower()
                    if (role == 'user' and not include_user) or (role == 'assistant' and not include_assistant):
                        continue
                    t = _extract_message_text(m)
                    if t:
                        texts.append(f"{role.upper()}: {t}")
            if not texts and isinstance(conv.get('messages'), list):
                for m in conv['messages']:
                    role = (m.get('role') or 'unknown').lower()
                    if (role == 'user' and not include_user) or (role == 'assistant' and not include_assistant):
                        continue
                    t = _extract_message_text(m)
                    if t:
                        texts.append(f"{role.upper()}: {t}")
            if not texts:
                continue
            header = f"[CONV: {title}]\n"
            full = header + "\n\n".join(texts)
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
    ap.add_argument('-i','--input', required=True, help='OpenAI conversations.json path or directory')
    ap.add_argument('-o','--outdir', required=True, help='Output directory')
    ap.add_argument('-m','--model', default=os.getenv('OPENAI_MODEL','gpt-5'))
    ap.add_argument('--roles', choices=['both','user','assistant'], default='both')
    args = ap.parse_args()
    
    include_user = args.roles in ('both','user')
    include_assistant = args.roles in ('both','assistant')

    if not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('OPENAI_API_KEY is not set. Provide via GUI or .env')

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    jsonl_path = outdir / 'scan_quotes.jsonl'

    client = OpenAI()
    seen = set()
    csv_path = outdir / 'quotes_index.csv'
    
    with open(jsonl_path, 'w', encoding='utf-8') as jf, open(csv_path, 'w', newline='', encoding='utf-8') as cf:
        cw = csv.writer(cf)
        cw.writerow(['page_start','page_end','category','top_tag','preview','conversation'])

        for inp in iter_inputs(args.input):
            pages = load_pages_from_openai_json_one(inp, include_user, include_assistant)
            chunks = chunk_pages(pages)
            for p_start, p_end, text in tqdm(chunks, desc=f'Scanning {os.path.basename(inp)}'):
                recs = extract_quotes(client, args.model, text, p_start, p_end)
                conv_match = re.search(r'\[CONV:\s*(.*?)\]', text)
                conv_title = conv_match.group(1).strip() if conv_match else ''
                for r in recs:
                    key = norm_key(r['quote'])
                    if key in seen:
                        continue
                    seen.add(key)
                    r_out = dict(r); r_out['conversation'] = conv_title  # keep convo label
                    jf.write(json.dumps(r_out, ensure_ascii=False) + '\n')
                    cw.writerow([r['page_start'], r['page_end'], r.get('category',''),
                                 (r.get('tags') or [''])[0], r['quote'][:80].replace('\n',' '), conv_title])

    print(f"Wrote verified quotes → {jsonl_path}")
    print(f"Wrote CSV index → {csv_path}")

if __name__ == '__main__':
    main()
