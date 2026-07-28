# Architectural Dissection: Shifting to a Layout-Aware Spatial Pipeline

This document outlines the exact technical roadmap for migrating our extraction engine away from brittle linear text reading (`pdfplumber`) and towards a true spatial-geometry solution. This transition aims to mitigate the "GIGO" (Garbage In, Garbage Out) bottleneck, allowing the 70B AI model to receive highly structured Markdown tables.

---

## Phase 1: Grid Cropping & Noise Reduction
**The Goal:** Bank statements are heavily polluted with marketing banners, branch addresses, and dynamic page footers. We must strip this out mathematically before the layout parser even looks at the page.

**How to Implement:**
1.  **Anchor Detection:** We will still use `pdfplumber` or `PyMuPDF (fitz)`, but *only* for its bounding-box coordinate engine. 
2.  **Y-Axis Slicing:** 
    *   We scan the page for the word `Date` or `Transaction Date`. We record its `Y-Top` coordinate.
    *   We scan the bottom of the page for `Closing Balance` or the final line of the table. We record its `Y-Bottom` coordinate.
3.  **The Crop:** We programmatically execute a `pdf.crop((0, y_top, page_width, y_bottom))` command. This yields a noise-reduced grid containing the transactions. 
    *   *Note:* This is preprocessing only. It removes top/bottom noise but won't handle banners, ads, or other non-table content that appears *inside* the transaction bounds. Phase 2's layout detection will be responsible for isolating the actual table.

---

## Phase 2: Replacing `pdfplumber` with a Spatial Engine
**The Goal:** Stop reading left-to-right (which squashes tightly packed "Debit" and "Balance" columns together) and start reading the structural whitespace of the page.

**How to Implement:**
1.  **Benchmarking the Spatial Engine:**
    *   Instead of assuming one tool is superior, we will benchmark modern deep-learning models (like IBM's **Docling** or **Marker-PDF**) against specialized classical tools like **Camelot** (using `flavor='stream'`).
    *   These tools calculate whitespace and output structural layouts (e.g., `| 01-Jan-2024 | Transfer | 500 | 1000 |`).
2.  **Selection Strategy:**
    *   We will test these engines on a representative set of our most complex bank statements. The tool that most accurately preserves table structures will be selected as the primary parser, and a fallback will only be implemented if testing justifies the added complexity.

---

## Phase 3: Structured Handoff to Llama-3.3-70b
**The Goal:** Change the AI's job from "Guessing Layouts" to "Semantic Data Structuring."

**How to Implement:**
1.  **Prompt Refactoring:** We rip out all prompt engineering related to spatial parsing (e.g., *"Try to guess where the description ends"*). 
2.  **The Input:** We feed the LLM the structured Markdown table generated in Phase 2. 
3.  **The Task:** We re-task the 70B model to focus exclusively on its core strengths:
    *   **Semantic Classification:** Mapping the rows to Pydantic objects.
    *   **Expansion:** Expanding abbreviations (`IBFT` -> `Inter-Bank Fund Transfer`).
    *   **Translation:** Seamlessly translating the clean text into the user's target language.
    *   **JSON Enforcement:** Returning strict JSON arrays ready for the Web UI.

---

## Phase 4: Validating via the Mathematical Gate
**The Goal:** Acknowledge that even with a perfect layout parser, real-world data is inherently flawed (e.g., banks omitting fees from running balances).

**How to Implement:**
1.  **Preserve the Math Gate:** Our strict `Previous Balance + Credit - Debit = New Balance` Reconciliation Engine remains untouched.
2.  **Human-in-the-Loop Integration:** If the layout engine or AI misses a row, the Math Gate throws a `balance_mismatch`. The user corrects the specific cell in the UI, re-validates, and exports. 

### Conclusion
By executing this shift, we address the spatial geometry problem using actual geometric tools (Docling/Camelot), rather than forcing natural language models to act as eyes. This aims to provide the highest possible quality of data entering the AI, drastically reducing hallucinations and setting a realistic target for high reliability in production.
