# OpenAI Research Scanner

<div align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="logo-light.svg" />
    <source media="(prefers-color-scheme: light)" srcset="logo-dark.svg" />
    <img src="logo-dark.svg" alt="OpenAI Research Scanner" width="120" height="120">
  </picture>
</div>

Windows-first toolkit that mines PDFs and GPT chat exports for **verbatim** quotes, builds research compilations, and reconstructs app/tool ideas — with **cost-aware** token estimates/caps, **streaming** JSON support, and a **CSV index**.

---

## Features

- **Dual Input (PDF + JSON)**  
  Scan PDFs **or** OpenAI ChatGPT exports (`conversations.json` or a folder of JSON files).

- **Streaming & Directory Mode**  
  Handles very large exports via `ijson` streaming; process a single file or an entire directory.

- **Role Filtering (JSON)**  
  Choose **Both**, **User only**, or **Assistant only** to focus the signal.

- **Quote-Only Extraction + Verification**  
  Extracts exact spans only (no paraphrasing) and verifies every quote against source text.

- **Cost-Aware GPT Runs**  
  Token & $ **estimation** before heavy calls, **thresholded auto-run**, and per-run `cost_report.json`.

- **Organized Outputs**  
  Themed **compilations** and **long snippets** (Markdown) with page refs + an `INDEX.md`.

- **Apps & Tools Reconstruction**  
  Generates a clean list of product/tool ideas with concise titles, summaries, deduped items, and evidence pages/quotes.

- **Windows GUI**  
  PowerShell-based interface with logging, model pickers, role filter, and one-click workflows.

---

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <your-repo-link>
   cd <repo-folder>
