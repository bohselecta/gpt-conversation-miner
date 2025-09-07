import os, json, argparse, pathlib, re, unicodedata, glob
from typing import List, Dict, Set
from tqdm import tqdm
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

CHARS_PER_CHUNK = 9000
PSEUDO_PAGE_SIZE = 2500

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
    """Normalize text for comparison."""
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()

def deduplicate_quotes(quotes: List[Dict], similarity_threshold: int = 5) -> List[Dict]:
    """Remove near-duplicate quotes based on normalized text similarity."""
    seen: Set[str] = set()
    unique_quotes = []
    
    for quote in quotes:
        normalized = normalize_text(quote.get('quote', ''))
        if not normalized:
            continue
            
        # Check for near-duplicates
        is_duplicate = False
        for seen_text in seen:
            if abs(len(normalized) - len(seen_text)) <= similarity_threshold:
                # Simple similarity check - could be enhanced with fuzzy matching
                if normalized in seen_text or seen_text in normalized:
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            seen.add(normalized)
            unique_quotes.append(quote)
    
    return unique_quotes

def load_pages_from_json_streaming(path: str) -> List[str]:
    """Load pages using streaming JSON parser for large files."""
    try:
        import ijson
        return _load_with_ijson(path)
    except (ImportError, NameError):
        # Fallback to regular JSON loading
        return _load_with_regular_json(path)

def _load_with_ijson(path: str) -> List[str]:
    """Load using ijson streaming parser."""
    pages: List[str] = []
    
    with open(path, 'rb') as f:
        # Parse conversations array
        conversations = ijson.items(f, 'item')
        for idx, conv in enumerate(conversations, start=1):
            title = conv.get('title') or f'Conversation {idx}'
            texts: List[str] = []
            
            # Process mapping if present
            mapping = conv.get('mapping')
            if isinstance(mapping, dict):
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
            
            # Fallback to messages
            if not texts and isinstance(conv.get('messages'), list):
                for m in conv['messages']:
                    t = _extract_message_text(m)
                    if t:
                        role = (m.get('role') or 'unknown').upper()
                        texts.append(f"{role}: {t}")
            
            if texts:
                header = f"[CONV: {title}]\n"
                full = header + "\n\n".join(texts)
                
                # Split into pseudo-pages
                for off in range(0, len(full), PSEUDO_PAGE_SIZE):
                    pages.append(full[off:off+PSEUDO_PAGE_SIZE])
    
    return pages

def _load_with_regular_json(path: str) -> List[str]:
    """Fallback to regular JSON loading."""
    p = pathlib.Path(path)
    data = json.loads(p.read_text(encoding='utf-8'))
    convs = data if isinstance(data, list) else data.get('conversations') or []
    pages: List[str] = []

    for idx, conv in enumerate(convs, start=1):
        title = conv.get('title') or f'Conversation {idx}'
        texts: List[str] = []

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

        if not texts and isinstance(conv.get('messages'), list):
            for m in conv['messages']:
                t = _extract_message_text(m)
                if t:
                    role = (m.get('role') or 'unknown').upper()
                    texts.append(f"{role}: {t}")

        if texts:
            header = f"[CONV: {title}]\n"
            full = header + "\n\n".join(texts)
            for off in range(0, len(full), PSEUDO_PAGE_SIZE):
                pages.append(full[off:off+PSEUDO_PAGE_SIZE])

    return pages

def _extract_message_text(msg: Dict) -> str:
    """Extract text from message content."""
    if not isinstance(msg, dict):
        return ''
    cont = msg.get('content')

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

def chunk_pages(pages: List[str], chars_per_chunk=CHARS_PER_CHUNK):
    """Chunk pages into manageable sizes."""
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

def extract_quotes(client: OpenAI, model: str, chunk_text: str, p_start: int, p_end: int) -> List[Dict]:
    """Extract quotes from chunk using OpenAI."""
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
        for line in txt.splitlines():
            line = line.strip()
            if line.startswith('{') and line.endswith('}'):
                try:
                    q = Quote(**json.loads(line)).model_dump()
                    records.append(q)
                except Exception:
                    pass

    # Verify quotes are verbatim
    norm_chunk = normalize_text(chunk_text)
    verified = []
    for r in records:
        qnorm = normalize_text(r['quote'])
        if qnorm and qnorm in norm_chunk:
            r['page_start'] = max(p_start, int(r['page_start']))
            r['page_end'] = min(p_end, int(r['page_end']))
            verified.append(r)
    return verified

def load_json_files(input_path: str) -> List[str]:
    """Load JSON files - supports both single file and directory."""
    path = pathlib.Path(input_path)
    
    if path.is_file():
        return load_pages_from_json_streaming(str(path))
    elif path.is_dir():
        # Load all JSON files in directory
        json_files = list(path.glob("*.json"))
        json_files = [f for f in json_files if f.name != "index.html"]  # Skip index
        
        all_pages = []
        for json_file in json_files:
            print(f"Loading {json_file.name}...")
            pages = load_pages_from_json_streaming(str(json_file))
            all_pages.extend(pages)
        
        return all_pages
    else:
        raise FileNotFoundError(f"Path not found: {input_path}")

def main():
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument('-i','--input', required=True, help='OpenAI conversations.json path or directory')
    ap.add_argument('-o','--outdir', required=True, help='Output directory')
    ap.add_argument('-m','--model', default=os.getenv('OPENAI_MODEL','gpt-5'))
    ap.add_argument('--dedupe', action='store_true', help='Remove duplicate quotes')
    ap.add_argument('--dedupe-threshold', type=int, default=5, help='Character threshold for deduplication')
    args = ap.parse_args()

    if not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('OPENAI_API_KEY is not set. Provide via GUI or .env')

    outdir = pathlib.Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    jsonl_path = outdir / 'scan_quotes.jsonl'

    print(f"Loading JSON files from: {args.input}")
    pages = load_json_files(args.input)
    print(f"Loaded {len(pages)} pages")
    
    chunks = chunk_pages(pages)
    print(f"Created {len(chunks)} chunks")
    
    client = OpenAI()

    all_quotes = []
    with open(jsonl_path, 'w', encoding='utf-8') as f:
        for p_start, p_end, text in tqdm(chunks, desc='Scanning JSON'):
            recs = extract_quotes(client, args.model, text, p_start, p_end)
            all_quotes.extend(recs)

    # Deduplicate if requested
    if args.dedupe:
        print(f"Before deduplication: {len(all_quotes)} quotes")
        all_quotes = deduplicate_quotes(all_quotes, args.dedupe_threshold)
        print(f"After deduplication: {len(all_quotes)} quotes")
        
        # Rewrite file with deduplicated quotes
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for quote in all_quotes:
                f.write(json.dumps(quote, ensure_ascii=False) + '\n')

    print(f"Wrote {len(all_quotes)} verified quotes → {jsonl_path}")

if __name__ == '__main__':
    main()
