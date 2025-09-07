#!/usr/bin/env python3
"""Generate CSV index for quick grepping of quotes."""

import json
import csv
import pathlib
import argparse

def generate_csv_index(jsonl_path: pathlib.Path, output_path: pathlib.Path):
    """Generate CSV index from scan_quotes.jsonl."""
    quotes = []
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                quote = json.loads(line)
                quotes.append(quote)
            except json.JSONDecodeError:
                continue
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['page_start', 'page_end', 'category', 'top_tag', 'preview', 'full_quote'])
        
        for quote in quotes:
            page_start = quote.get('page_start', 0)
            page_end = quote.get('page_end', 0)
            category = quote.get('category', 'unknown')
            tags = quote.get('tags', [])
            top_tag = tags[0] if tags else 'untagged'
            full_quote = quote.get('quote', '')
            preview = full_quote[:80] + '...' if len(full_quote) > 80 else full_quote
            
            writer.writerow([page_start, page_end, category, top_tag, preview, full_quote])
    
    print(f"Generated CSV index with {len(quotes)} quotes → {output_path}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', required=True, help='scan_quotes.jsonl path')
    ap.add_argument('-o', '--output', required=True, help='Output CSV path')
    args = ap.parse_args()
    
    jsonl_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output)
    
    if not jsonl_path.exists():
        print(f"Error: {jsonl_path} not found")
        return
    
    generate_csv_index(jsonl_path, output_path)

if __name__ == '__main__':
    main()
