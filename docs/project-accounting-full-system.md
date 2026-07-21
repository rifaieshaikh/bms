# Project Accounting Full System Checklist

Tracks UC-000A→044 and AC-001→015 against the 8-wave roadmap.

## Wave status

| Wave | Focus | Status |
|------|-------|--------|
| 1 | Foundation (roles, dimensions, audit, config) | Implemented |
| 2 | Commercial wizard / quotations / contract | Implemented |
| 3 | Budget / control overview | Implemented |
| 4 | Execution / DPR / quality | Implemented |
| 5 | Procurement / stock / subcontract | Implemented |
| 6 | Measurement / RA / variations | Implemented |
| 7 | Settlement / retention / closure | Implemented |
| 8 | Advanced finance / mobile / portal | Implemented |

## Acceptance criteria

| ID | Criterion | Status |
|----|-----------|--------|
| AC-001 | Quotation → baseline with history | Pass (Waves 1–2) |
| AC-002 | Separate progress facts | Pass (Wave 3 overview 6-fact strip) |
| AC-003 | Line-level project dimensions | Pass (Wave 1 expense/time) |
| AC-004 | Budget actual/committed/forecast | Pass (Wave 3) |
| AC-005 | Activity transition guards | Pass (Wave 4) |
| AC-006 | No double-bill certified qty | Pass (Wave 6) |
| AC-007 | RA previous/current/cumulative | Pass (Wave 6) |
| AC-008 | Advance/TDS/retention/short-pay visible | Pass (Wave 7) |
| AC-009 | Customer-on-behalf ownership | Pass (Wave 5–7) |
| AC-010 | Balanced journals + drill-down | Pass (Wave 8 recognition post + reconcile UI) |
| AC-011 | Revise don't overwrite | Pass (Wave 1 quotes) |
| AC-012 | Closure blockers | Pass (Wave 7) |
| AC-013 | Cost/margin permissions | Pass (Wave 1) |
| AC-014 | Idempotent DPR | Pass (Wave 4) |
| AC-015 | Mobile site capture | Pass (Wave 8 site mobile + offline drafts) |

## Wave 8 coverage notes

- Recognition `post` creates WIP/Revenue journal via accounting when available, else stores balanced `journal_stub`.
- Overhead allocation posts HO OH expense from `overhead_allocation_pct`.
- Reconcile UI: create / list reconciliations + books_match captions (UC-044).
- Site mobile + offline draft queue; customer portal tokens; currency stub (`INR`); notification stub; integration webhook docs.
