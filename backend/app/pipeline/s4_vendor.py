from ..models import Vendor
from ..util import name_score
from .base import StageResult, chk

NAME = "Vendor check"


def run(ctx):
    r = StageResult()
    c = r.checks
    cfg, ex = ctx.cfg, ctx.ex
    F = ex["fields"]
    vendors = ctx.db.vendors()
    by_gstin = next((v for v in vendors if F.get("vendor_gstin") and v.gstin == F["vendor_gstin"]), None)
    scored = sorted(((name_score(F.get("vendor_name") or "", v.legal_name), v) for v in vendors), key=lambda x: -x[0])
    best_score, best = (scored[0] if scored else (0, None))
    by_name = best if best_score >= cfg.vendor_name_possible else None
    vendor = by_gstin or by_name
    if by_gstin:
        c.append(chk("R4.1", "Vendor identified", "pass", f"Matched {by_gstin.vendor_id} {by_gstin.legal_name} by GSTIN"))
    elif by_name and best_score >= cfg.vendor_name_match:
        c.append(chk("R4.1", "Vendor identified", "pass", f"Matched {by_name.vendor_id} {by_name.legal_name} by name (score {best_score:.0f})"))
    elif by_name:
        c.append(chk("R4.1", "Vendor identified", "warn", f"Possible match {by_name.vendor_id} {by_name.legal_name} (name score {best_score:.0f}, needs >= {cfg.vendor_name_match})"))
    else:
        c.append(chk("R4.1", "Vendor identified", "fail",
                     f"No vendor in the master matches '{F.get('vendor_name')}' (best name score {best_score:.0f})"))
    if vendor is None:
        r.summary = "Vendor not found in the vendor master"
        r.data = {"vendor_id": None}
        ctx.vendor = None
        return r.finalise()
    ctx.vendor = vendor
    c.append(chk("R4.2", "Vendor approved", "pass" if vendor.approval_status == "Approved" else "fail",
                 f"{vendor.legal_name} is {vendor.approval_status}"))
    if F.get("vendor_gstin"):
        ok = F["vendor_gstin"] == vendor.gstin
        c.append(chk("R4.3", "GSTIN matches master", "pass" if ok else "fail",
                     f"{F['vendor_gstin']} equals master" if ok else f"Invoice GSTIN {F['vendor_gstin']} differs from master {vendor.gstin}"))
    else:
        c.append(chk("R4.3", "GSTIN matches master", "pass", "No GSTIN legible on invoice; vendor identified by name"))
    if by_gstin and by_name and by_gstin.vendor_id != by_name.vendor_id and best_score >= cfg.vendor_name_match:
        c.append(chk("R4.4", "GSTIN and name agree", "fail",
                     f"GSTIN points to {by_gstin.vendor_id} but the name points to {by_name.vendor_id}"))
    else:
        c.append(chk("R4.4", "GSTIN and name agree", "pass", "GSTIN lookup and name lookup agree"))
    bank = ex["bank"]
    if bank.get("account") or bank.get("ifsc"):
        acc_ok = (not bank.get("account")) or bank["account"] == vendor.bank_account_no
        ifsc_ok = (not bank.get("ifsc")) or bank["ifsc"] == vendor.ifsc
        confs = [bank.get("account_conf", 1.0) if bank.get("account") else 1.0, bank.get("ifsc_conf", 1.0) if bank.get("ifsc") else 1.0]
        if acc_ok and ifsc_ok:
            c.append(chk("R4.5", "Bank details match master", "pass", "Account number and IFSC equal the vendor master"))
        elif min(confs) < cfg.min_confidence_critical:
            c.append(chk("R4.5", "Bank details match master", "warn",
                         f"Bank details differ from master but were read with low confidence ({min(confs):.2f}); verify manually"))
        else:
            c.append(chk("R4.5", "Bank details match master", "fail",
                         f"Bank account on invoice ({bank.get('account')}, {bank.get('ifsc')}) differs from master: possible payment fraud"))
    else:
        c.append(chk("R4.5", "Bank details match master", "pass", "No bank details on invoice (pass with a note)"))
    sc = name_score(F.get("vendor_name") or "", vendor.legal_name)
    c.append(chk("R4.6", "Vendor name matches master", "pass" if sc >= cfg.vendor_name_match else "warn",
                 f"Name score {sc:.0f} against '{vendor.legal_name}'"))
    r.data = {"vendor_id": vendor.vendor_id, "legal_name": vendor.legal_name, "state_code": vendor.state_code,
              "approval_status": vendor.approval_status, "name_score": sc}
    r.summary = (f"{vendor.legal_name} ({vendor.vendor_id}) is {vendor.approval_status.lower()}; "
                 f"{'GSTIN and bank match' if all(x['result']=='pass' for x in c) else 'see flagged checks'}")
    return r.finalise()
