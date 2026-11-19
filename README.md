# InvoiceIQ — invoice PDF to reasoned decision

A live web process for the Zamp ASA case study, problem statement PS-1 (Finance / AP). Upload a vendor invoice PDF (text or scanned) and InvoiceIQ runs it through nine visible stages and returns **Approve, Review or Reject** with a plain-English reason and the rule id that decided it.

**Principle: AI reads, rules decide.** Extraction is local (pdfplumber text layer, or PyMuPDF + Tesseract OCR for scans) and every verdict comes from a deterministic rule table. No API key and no external calls are needed. The same invoice always produces the same decision.

## The nine stages
1 Ingest · 2 Extract · 3 Validate completeness · 4 Vendor check · 5 Duplicate check · 6 PO match · 7 Three-way numeric check · 8 Decide · 9 Output.
All stages run whenever extraction produced anything ("keep going, then decide") so the reason lists every problem. A crashed stage is isolated and routes the invoice to Review. Unknown rules fail safe to Review, never to Approve.

## Edge cases built in (samples S01–S10 on the Upload page)
| Sample | Case | Expected |
|---|---|---|
| S03 then S04 | **Split PO**: one PO billed over several invoices; balance 180,000 → 80,000, then a 95,000 invoice overruns by 5% | Approve, then Review (R7.7) |
| S05 | **Implied PO**: no PO printed; scored by amount, description, line match and timing | Review (R8.2) |
| S06 | **Duplicate resubmission** in a new layout and number style (INV/MFS/2210 vs INV-MFS-2210) | Reject (R5.1) |
| S07 | **Scanned / incomplete**: image-only, rotated, invoice number smudged, total illegible | Review (R3.1, R7.3) |
| S01, S02, S08, S09, S10 | happy path, 4% price variance, blocked vendor, closed PO, wrong tax type | Approve, Review, Reject, Reject, Review |

After all ten: 2 Approve, 5 Review, 3 Reject. Run S03 before S04. Use **Reference Data → Reset demo data** to start over. Re-uploading the same file is rejected as a duplicate (R5.2).

## Pages
- **Upload & Run**: step flow (load data, validate, configure, run), last-run banner, drop zone, ten sample invoices, six reference-data cards, a data readiness score (Schema, Completeness, Consistency), pre-run insights and a validation log.
- **Live run**: nine stage cards, expandable checks, decision card, rule trail, override, run report PDF, vendor letter PDF. The matched PO links to its balance view.
- **Configuration**: slider cards with ACTIVE values, pipeline stage guide (owner and turnaround), formulas and decision logic, the full rule table.
- **Dashboard**: vendor filter, metric definitions, 12 KPI tiles, decisions, trend, value by decision, stage funnel, time per stage, rule hits, extraction confidence, vendor risk, vendor x cause matrix, largest flagged invoices, activity feed.
- **Action Tracker**: critical / needs-a-decision / resolved / value-at-risk cards, nine stage buckets (click to filter) with owner and turnaround, one ranked queue with SLA flag and editable assignee and status, activity log.
- **Run History** (filter, search, CSV) and **Reference Data** (vendors, POs with a PO balance view, invoice register, reset).
