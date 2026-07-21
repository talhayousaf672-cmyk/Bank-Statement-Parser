# Architectural Dissection: Shifting to a Layout-Aware Spatial Pipeline

This document outlines the exact technical roadmap for migrating our extraction engine away from brittle linear text reading (`pdfplumber`) and towards a true spatial-geometry solution. This transition will surgically remove the "GIGO" (Garbage In, Garbage Out) bottleneck, allowing the 70B AI model to receive perfectly spaced Markdown tables.

---

## Phase 1: Grid Cropping & Noise Reduction
**The Goal:** Bank statements are heavily polluted with marketing banners, branch addresses, and dynamic page footers. We must strip this out mathematically before the layout parser even looks at the page.

**How to Implement:**
1.  **Anchor Detection:** We will still use `pdfplumber` or `PyMuPDF (fitz)`, but *only* for its bounding-box coordinate engine. 
2.  **Y-Axis Slicing:** 
    *   We scan the page for the word `Date` or `Transaction Date`. We record its `Y-Top` coordinate.
    *   We scan the bottom of the page for `Closing Balance` or the final line of the table. We record its `Y-Bottom` coordinate.
3.  **The Crop:** We programmatically execute a `pdf.crop((0, y_top, page_width, y_bottom))` command. This yields a mathematically pure, noise-free grid containing *only* the transactions.

---

## Phase 2: Replacing `pdfplumber` with a Spatial Engine
**The Goal:** Stop reading left-to-right (which squashes tightly packed "Debit" and "Balance" columns together) and start reading the structural whitespace of the page.

**How to Implement:**
1.  **Primary Framework Evaluation (Docling vs Marker):**
    *   Integrate IBM's `Docling` or `Marker-PDF`. These are specialized deep-learning models designed exclusively to look at document geometry and output structural Markdown.
    *   Instead of feeding the AI `01-Jan-2024 Transfer 500 1000`, these tools naturally calculate the whitespace and output: `| 01-Jan-2024 | Transfer | 500 | 1000 |`.
2.  **Deterministic Fallback (Camelot):**
    *   If the AI layout parsers fail on heavily gridded statements, we implement `camelot-py` using `flavor='stream'`. 
    *   Camelot uses agglomerative clustering to find empty vertical rivers of whitespace and mathematically draws invisible column boundaries between them, bypassing the need for NLP completely.

---

## Phase 3: Structured Handoff to Llama-3.3-70b
**The Goal:** Change the AI's job from "Guessing Layouts" to "Semantic Data Structuring."

**How to Implement:**
1.  **Prompt Refactoring:** We rip out all prompt engineering related to spatial parsing (e.g., *"Try to guess where the description ends"*). 
2.  **The Input:** We feed the LLM the pristine Markdown table generated in Phase 2. 
3.  **The Task:** We re-task the 70B model to focus exclusively on its true strengths:
    *   **Semantic Classification:** Mapping the rows to Pydantic objects.
    *   **Expansion:** Expanding abbreviations (`IBFT` -> `Inter-Bank Fund Transfer`).
    *   **Translation:** Seamlessly translating the clean text into the user's target language.
    *   **JSON Enforcement:** Returning perfect, strict JSON arrays ready for the Web UI.

---

## Phase 4: Validating via the Mathematical Gate
**The Goal:** Acknowledge that even with a perfect layout parser, real-world data is inherently flawed (e.g., banks omitting fees from running balances).

**How to Implement:**
1.  **Preserve the Math Gate:** Our strict `Previous Balance + Credit - Debit = New Balance` Reconciliation Engine remains untouched.
2.  **Human-in-the-Loop Integration:** If the layout engine or AI misses a row, the Math Gate throws a `balance_mismatch`. The user corrects the specific cell in the UI, re-validates, and exports. 

### Conclusion
By executing this shift, we resolve the spatial geometry problem using actual geometric tools (Docling/Camelot), rather than forcing natural language models to act as eyes. This guarantees the highest possible quality of data entering the AI, drastically reducing hallucinations and paving the way for 90%+ zero-touch reliability in production.
