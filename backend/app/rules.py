"""Rule table (Section 5 of the spec). Each rule maps a check result to a level.

Levels: REJECT (blocks, return to vendor) | REVIEW (needs a human) | INFO (shown, does not block).
Fail-safe: an unknown rule id or an 'error' result is Review-level (R8.5).
"""

R = {}


def _r(rid, stage, name, fail=None, warn=None, desc=""):
    R[rid] = {"id": rid, "stage": stage, "name": name, "fail": fail, "warn": warn, "description": desc}


# Stage 1
_r("R1.1", 1, "File is a readable PDF", fail="REJECT", desc="Starts with %PDF- and has a .pdf extension")
_r("R1.2", 1, "File size limit", fail="REJECT", desc="At most 10 MB")
_r("R1.3", 1, "Page count limit", warn="INFO", desc="At most 10 pages; only the first 10 are read")
_r("R1.4", 1, "Not password protected", fail="REJECT", desc="Encrypted PDFs are returned to the vendor")
_r("R1.5", 1, "Reading path", desc="Text density >= 80 chars/page reads text, otherwise OCR scan path")
_r("R1.6", 1, "File not seen before", warn="INFO", desc="SHA-256 already processed (final call is Stage 5)")
# Stage 2
_r("R2.1", 2, "Extraction produced a record", fail="REVIEW", desc="Extractor returned a usable invoice object")
_r("R2.3", 2, "Dates are real dates", warn="REVIEW", desc="Date fields parse to calendar dates")
_r("R2.5", 2, "Extraction confidence", warn="INFO", fail="REVIEW", desc="Overall >= 0.90 pass, critical fields >= 0.80")
# Stage 3
_r("R3.1", 3, "Required fields present", fail="REVIEW", desc="Invoice number, date, vendor name and total are all present")
_r("R3.2", 3, "Invoice number format", fail="REVIEW", desc="1-25 chars, letters/digits/hyphen/slash/space, not a placeholder")
_r("R3.3", 3, "Invoice date is sensible", fail="REVIEW", warn="INFO", desc="Not in the future; older than 180 days or due before invoice is a warning")
_r("R3.4", 3, "Vendor GSTIN format", fail="REVIEW", desc="15-character GSTIN pattern with state code 01-38")
_r("R3.5", 3, "Total amount valid", fail="REVIEW", warn="INFO", desc="Total > 0, INR currency")
_r("R3.6", 3, "IFSC format", warn="INFO", desc="Four letters, a zero, six characters")
_r("R3.7", 3, "Billed to Helix Retail", fail="REJECT", desc="Buyer GSTIN equals 27AAACH1111A1Z7")
_r("R3.8", 3, "Line items complete", warn="INFO", desc="Each line has a description and a quantity or amount")
_r("R3.9", 3, "Critical field confidence", warn="REVIEW", desc="Every critical field read with confidence >= 0.80")
# Stage 4
_r("R4.1", 4, "Vendor identified", fail="REJECT", warn="REVIEW", desc="GSTIN exact match or name score >= 92 (80-91 warns)")
_r("R4.2", 4, "Vendor approved", fail="REJECT", desc="approval_status is Approved")
_r("R4.3", 4, "GSTIN matches master", fail="REJECT", desc="GSTIN on invoice equals master")
_r("R4.4", 4, "GSTIN and name agree", fail="REJECT", desc="Both lookups resolve to the same vendor")
_r("R4.5", 4, "Bank details match master", fail="REJECT", warn="REVIEW", desc="Account number and IFSC equal master (possible payment fraud if not)")
_r("R4.6", 4, "Vendor name matches master", warn="INFO", desc="Name score >= 92 against master legal name")
# Stage 5
_r("R5.1", 5, "Same invoice number (D1)", fail="REJECT", desc="Same vendor and same normalised invoice number")
_r("R5.2", 5, "Same file (D2)", fail="REJECT", desc="Identical SHA-256 already processed")
_r("R5.3", 5, "Same amount within 90 days (D3)", warn="REVIEW", desc="Same vendor and total within the duplicate window")
_r("R5.4", 5, "Near-identical number (D4)", warn="REVIEW", desc="Edit distance <= 1 and same total")
# Stage 6
_r("R6.1", 6, "Printed PO exists", warn="INFO", desc="Printed PO reference exists in the PO table; otherwise infer")
_r("R6.2", 6, "PO is open", fail="REJECT", desc="Matched PO status is Open")
_r("R6.3", 6, "PO belongs to vendor", fail="REJECT", desc="Matched PO belongs to the vendor from Stage 4")
_r("R6.4", 6, "Inferred PO is unambiguous", fail="REJECT", desc="Confidence >= 0.75 and lead >= 0.15")
_r("R6.5", 6, "Vendor has a candidate PO", fail="REJECT", desc="At least one open PO for the vendor")
_r("R6.6", 6, "Printed PO plausible", warn="REVIEW", desc="Printed PO scores < 0.40 while another scores >= 0.75")
# Stage 7
_r("R7.1", 7, "Line arithmetic", warn="REVIEW", desc="qty x unit price = amount within Rs 1.00")
_r("R7.2", 7, "Lines add up to subtotal", warn="REVIEW", desc="Sum of lines = subtotal within Rs 1.00")
_r("R7.3", 7, "Subtotal + tax = total", fail="REVIEW", desc="Within Rs 1.00; unreadable total fails")
_r("R7.4", 7, "Tax type is right", warn="REVIEW", desc="Same state as buyer => CGST+SGST, otherwise IGST")
_r("R7.5", 7, "Tax rate and amount", warn="REVIEW", desc="Rate equals PO GST rate; tax = subtotal x rate within Rs 1.00")
_r("R7.6", 7, "Line price within tolerance", warn="REVIEW", fail="REJECT", desc="<=2% pass, 2-10% review, >10% reject")
_r("R7.7", 7, "Cumulative PO overrun", warn="REVIEW", fail="REJECT", desc="(billed + this - PO) / PO: <=2% pass, 2-10% review, >10% reject")
_r("R7.8", 7, "Currency matches PO", fail="REJECT", desc="Invoice currency equals PO currency")
_r("R7.9", 7, "High-value invoice", warn="REVIEW", desc="Total above Rs 5,00,000 always needs a human")
# Stage 8
_r("R8.1", 8, "Decision order", desc="Reject > Review > Approve")
_r("R8.2", 8, "Inferred PO", warn="REVIEW", desc="An inferred PO always goes to Review")
_r("R8.3", 8, "Uncertain critical field", warn="REVIEW", desc="Any critical field below 0.80 confidence goes to Review")
_r("R8.4", 8, "High value", warn="REVIEW", desc="Total above the auto-approve limit goes to Review")
_r("R8.5", 8, "Fail-safe", warn="REVIEW", desc="Unknown rule or stage error counts as Review")
_r("R8.6", 8, "Reason text is grounded", desc="Wording accepted only if every number is in the facts")
# Stage 9
_r("R9.1", 9, "Atomic save", desc="Run, invoice row and follow-up item are saved in one transaction")
_r("R9.2", 9, "Overrides on Review only", desc="Override requires a note of 10+ characters")
_r("R9.3", 9, "Override is audited", desc="Updates decision, recalculates PO balance, writes audit row")
_r("R9.4", 9, "CSV columns fixed", desc="One row per run")

RULES = R
ORDER = {"REJECT": 0, "REVIEW": 1, "INFO": 2}


def level_of(rule_id, result):
    """Level for a check; unknown rule or error => REVIEW (fail-safe, R8.5)."""
    if result == "error":
        return "REVIEW"
    rule = R.get(rule_id)
    if rule is None:
        return "REVIEW"
    if result not in ("fail", "warn"):
        return None
    return rule.get(result) or "INFO"
