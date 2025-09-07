# Changelog

## [1.0.0] - 2025-01-07

### Added
- **Dual input support**: PDF and OpenAI `conversations.json` files
- **Quote-only extraction**: Verbatim quotes with post-verification against source text
- **Two post-processing modes**:
  - Compile with GPT (+ cost estimate): themed compilations & long snippets
  - Reconstruct Apps & Tools: deduped list with titles, summaries, evidence
- **Enterprise hardening**:
  - Streaming JSON parsing for huge files (>100MB)
  - Directory mode for processing multiple JSON files
  - Automatic quote deduplication to reduce token costs
  - CSV index generation for quick searching
  - Cost reporting with detailed token breakdowns
- **Role filtering**: User/Assistant/Both options for JSON scans
- **Cost controls**:
  - Token & $ estimation before running
  - Auto-run threshold for low-cost operations
  - Per-run `cost_report.json` files
- **Apps & Tools reconstruction**:
  - Fuzzy deduplication of similar apps (85% similarity threshold)
  - Evidence merging from duplicate sources
  - Structured JSON + Markdown output
- **GUI enhancements**:
  - Role filter dropdown
  - Cost threshold input
  - Apps & Tools reconstruction button
  - Real-time cost estimation

### Technical Features
- **Streaming JSON parsing**: Uses `ijson` for memory-efficient processing
- **Quote verification**: Normalizes and verifies quotes against source text
- **Conversation tracking**: Maintains source conversation titles
- **Cost estimation**: Uses `tiktoken` for accurate token counting
- **Error handling**: Graceful fallbacks for malformed data
- **Progress tracking**: Shows progress per file in directory mode

### Output Structure
```
output/<run>/
├── scan_quotes.jsonl          # Verified quotes with conversation labels
├── quotes_index.csv          # Searchable CSV index
├── cost_report.json          # Detailed cost breakdown
├── compilations/             # Quote compilations by category×tag
├── snippets/                 # Quote snippets by category×tag
├── apps_tools/               # Apps & tools reconstruction
│   ├── apps_and_tools.json   # Structured data
│   └── apps_and_tools.md     # Human-readable summary
└── INDEX.md                  # Navigation index
```

### Dependencies
- Python 3.10+
- OpenAI API (GPT-5, GPT-4o, variants)
- Windows 10/11
- PowerShell 5.1+

### Known Limitations
- OCR/PDF images need OCR pass (e.g., Tesseract) before scanning
- Quote matching is verbatim; stylized/encoded text may need normalization
- Extremely long JSON exports: streaming handles it, but estimates scale with content
- API usage is separate from ChatGPT Plus; costs are estimated and logged per run
