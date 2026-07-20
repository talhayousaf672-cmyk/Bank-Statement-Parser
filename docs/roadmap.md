# Bank Statement PDF Parsing Tool - Roadmap

This roadmap is normalized from the provided v2 plan.

## Shared Core

| Layer | Technology |
|---|---|
| PDF text extraction | PyMuPDF |
| RTL reordering | python-bidi, unicodedata |
| Schema | Pydantic |
| Parser architecture | Factory pattern with canonical internal model |
| Excel export | openpyxl |
| AI integration | Claude API for onboarding assist, fallback extraction, and description enrichment only |

Supported languages: Arabic, Urdu, Russian, Spanish, Hindi.

## Team

| Person | Role |
|---|---|
| Mohsin | Parsing Engine Lead |
| Umer | Validation & Data Lead |
| Talha | App & Localization Lead |

## Roadmap

1. Phase 0: foundation, schema, parser interface, fixtures, CI.
2. Phase 1: PDF extraction, RTL/LTR normalization, pilot parsers.
3. Phase 2: reconciliation, confidence scoring, review queues, QA harness.
4. Phase 3: Excel export and localization.
5. Phase 4: multi-bank expansion.
6. Phase 4.5: AI assist integrations.
7. Phase 5A: desktop app.
8. Phase 5B: web app and infrastructure.
9. Phase 6: hardening and QA.
10. Phase 7: launch.

## Risks

- The timeline depends mostly on the number of bank layouts.
- AI fallback must never bypass reconciliation.
- Web financial-data handling requires RLS and storage-expiry review.
- Running desktop and web in parallel may stretch a three-person team.
