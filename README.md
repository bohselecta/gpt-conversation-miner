# OpenAI Research Scanner

<div align="center">
  <img src="camera-shutter.svg" alt="OpenAI Research Scanner" width="120" height="120" style="filter: brightness(0) invert(1);">
</div>

A powerful Windows GUI application for extracting and compiling research insights from PDFs using OpenAI's GPT-5 series models.

## Features

- **PDF Quote Extraction**: Uses OpenAI GPT-5 series to extract direct quotes from PDFs
- **Cost-Aware Processing**: Built-in token counting and cost estimation before expensive operations
- **Quote Verification**: Validates extracted quotes against actual PDF content to prevent drift
- **Organized Output**: Creates structured compilations and snippets grouped by category and tags
- **Dual Compilation**: Support for both OpenAI and Ollama-based quote compilation
- **Windows GUI**: Easy-to-use PowerShell-based interface

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/openai/research-scanner.git
   cd research-scanner
   ```

2. **Run the application**:
   - Double-click `research-scanner.bat`
   - The script will automatically set up Python virtual environment and install dependencies

3. **Use the GUI**:
   - Enter your OpenAI API key
   - Select a PDF file
   - Click "Scan PDF with ChatGPT" to extract quotes
   - Click "Compile with GPT (+ cost estimate)" to generate organized outputs

## Prerequisites

- **Python 3.10+** (automatically detected by the launcher)
- **PowerShell 5.1+** (built into Windows 10/11)
- **OpenAI API key** (for PDF scanning and compilation)
- **Ollama** (optional, for local compilation)

## Project Structure

```
research-scanner/
├─ research-scanner.bat           # Main launcher
├─ .cursorrules                   # Cursor workspace config
├─ AGENTS.md                     # Agent documentation
├─ requirements.txt              # Python dependencies
├─ .env.example                  # Environment template
├─ prompts/                      # System prompts
│   ├─ scan_system.txt          # Quote extraction prompt
│   ├─ ollama_compile_system.txt # Ollama compilation prompt
│   └─ openai_compile_system.txt # OpenAI compilation prompt
├─ scripts/                      # Core scripts
│   ├─ gui.ps1                  # PowerShell GUI
│   ├─ scan_pdf.py             # PDF scanning with OpenAI
│   ├─ parse_with_ollama.py    # Ollama-based compilation
│   └─ parse_with_openai.py    # OpenAI-based compilation
└─ output/                      # Results directory
```

## How It Works

### Agent A: PDF Sweeper (OpenAI)
- Chunks PDF pages into manageable sections
- Extracts direct quotes that signal research ideas, whitepaper seeds, or directions
- Uses JSON object format with strict validation
- Verifies quotes against actual PDF content

### Agent B: Quote Compiler
- Groups quotes by category and lead tag
- Creates themed compilations and substantial snippets
- Maintains quote-only output (no paraphrasing)
- Generates organized markdown files with citations

## Cost Management

The application includes built-in cost estimation for OpenAI models:
- **GPT-5**: $1.25/M input, $10.00/M output
- **GPT-5-mini**: $0.25/M input, $2.00/M output  
- **GPT-5-nano**: $0.05/M input, $0.40/M output
- **GPT-4o-mini**: $0.60/M input, $2.40/M output

Cost estimates are shown before expensive operations with user confirmation.

## Troubleshooting

- **PowerShell execution policy**: Run the `.bat` as Administrator if scripts are blocked
- **Python not found**: Install Python 3.10+ from python.org and ensure it's in PATH
- **Empty quotes**: Reduce chunk size or ensure PDF contains selectable text
- **Ollama not found**: Set the path in the GUI or add to PATH

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

Additionally, OpenAI and its affiliates have been granted extended rights under the [OpenAI Collaboration Addendum](OPENAI_COLLABORATION_ADDENDUM.md).

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.
