#!/usr/bin/env python3
"""Generate cost report for a scan run."""

import json
import pathlib
import argparse
from scripts.parse_with_openai import load_quotes, group_key, estimate_tokens_and_cost, DEFAULT_PROMPT

def generate_cost_report(jsonl_path: pathlib.Path, output_path: pathlib.Path, model: str = 'gpt-5-mini'):
    """Generate cost report from scan_quotes.jsonl."""
    quotes = load_quotes(jsonl_path)
    
    if not quotes:
        print("No quotes found in JSONL")
        return
    
    # Group quotes
    groups = {}
    for q in quotes:
        key = group_key(q)
        if key not in groups:
            groups[key] = []
        groups[key].append(q)
    
    # Estimate costs
    estimate = estimate_tokens_and_cost(model, groups, DEFAULT_PROMPT)
    
    # Generate report
    report = {
        'model': model,
        'total_quotes': len(quotes),
        'total_groups': len(groups),
        'estimate': estimate,
        'cost_breakdown': {
            'input_tokens': estimate['input_tokens'],
            'output_tokens': estimate['output_tokens'],
            'usd_input': estimate['usd_input'],
            'usd_output': estimate['usd_output'],
            'usd_total': estimate['usd_total']
        },
        'groups': []
    }
    
    # Add group details
    for key, items in groups.items():
        group_estimate = estimate_tokens_and_cost(model, {key: items}, DEFAULT_PROMPT)
        report['groups'].append({
            'name': key,
            'quote_count': len(items),
            'estimated_tokens': group_estimate['input_tokens'] + group_estimate['output_tokens'],
            'estimated_cost': group_estimate['usd_total']
        })
    
    # Write report
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"Generated cost report → {output_path}")
    print(f"Total quotes: {len(quotes)}")
    print(f"Total groups: {len(groups)}")
    if estimate['usd_total']:
        print(f"Estimated cost: ${estimate['usd_total']:.4f}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-i', '--input', required=True, help='scan_quotes.jsonl path')
    ap.add_argument('-o', '--output', required=True, help='Output JSON path')
    ap.add_argument('-m', '--model', default='gpt-5-mini', help='Model for cost estimation')
    args = ap.parse_args()
    
    jsonl_path = pathlib.Path(args.input)
    output_path = pathlib.Path(args.output)
    
    if not jsonl_path.exists():
        print(f"Error: {jsonl_path} not found")
        return
    
    generate_cost_report(jsonl_path, output_path, args.model)

if __name__ == '__main__':
    main()
