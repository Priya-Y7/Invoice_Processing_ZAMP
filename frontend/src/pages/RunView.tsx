import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ChevronDown, ChevronRight, Download, ExternalLink, FileText, Mail, ShieldCheck, UserCheck, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, post, useRunStream } from "../api";
import { Banner, ConfBar, Modal, RESULT_LABEL, RESULT_TEXT, StatusDot, VerdictBadge } from "../components/ui";
import { STAGE_BLURB, STAGE_FULL, STAGE_NAMES, VERDICT, inr, ms } from "../lib";

const LEVEL_CHIP: Record<string, string> = { REJECT: "bg-bad-soft text-bad", REVIEW: "bg-warn-soft text-warn", INFO: "bg-bg text-muted" };

export default function RunView() {
  const { id } = useParams();
  const qc = useQueryClient();
  const { stages, done, started } = useRunStream(id);
  const detail = useQuery({ queryKey: ["run", id], queryFn: () => api(`/runs/${id}`), enabled: !!done, refetchOnMount: "always" });
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const [modal, setModal] = useState<null | "approve" | "reject">(null);
  const [flash, setFlash] = useState<null | string>(null);
  const finished = stages[9]?.status && !["running", "pending"].includes(stages[9].status);
  const runningNo = Object.entries(stages).find(([, s]) => s.status === "running")?.[0];

  useEffect(() => {
    if (!done) return;
    qc.invalidateQueries({ queryKey: ["stats"] }); qc.invalidateQueries({ queryKey: ["runs"] }); qc.invalidateQueries({ queryKey: ["exceptions"] });
    qc.invalidateQueries({ queryKey: ["pos"] });
  }, [done]);

  const res = detail.data?.result;
  const verdict = detail.data?.final_decision || done?.decision;

  return (
    <div className="space-y-5">
      <div className="card px-5 py-3.5 flex items-center gap-4">
        <div className="min-w-0">
          <div className="font-semibold truncate flex items-center gap-2"><FileText size={16} className="text-muted" />{detail.data?.filename || res?.filename || "Invoice"}</div>
          <div className="text-[12px] text-muted flex items-center gap-3">{id}<a href={`/api/runs/${id}/file`} target="_blank" rel="noreferrer" className="text-indigo font-semibold inline-flex items-center gap-1 hover:underline"><ExternalLink size={12} />View invoice PDF</a></div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          {STAGE_NAMES.map((n, i) => {
            const s = stages[i + 1]?.status || "pending";
            return (
              <div key={n} className="flex items-center">
                <div className="flex flex-col items-center w-[62px]"><StatusDot s={s} size={22} /><span className={`text-[10.5px] mt-1 ${s === "running" ? "text-indigo font-semibold" : "text-muted"}`}>{n}</span></div>
                {i < 8 && <div className={`h-0.5 w-4 -mt-4 ${stages[i + 1] && !["running", "pending"].includes(stages[i + 1].status) ? "bg-ok/50" : "bg-line"}`} />}
              </div>
            );
          })}
        </div>
        <div className="text-right text-[12px] text-muted shrink-0">
          {done ? <>Finished in <b className="text-ink">{ms(done.total_ms)}</b></> : started ? <span className="text-indigo font-medium">Running stage {runningNo || "…"} of 9</span> : "Queued"}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-5 items-stretch">
        <div className="col-span-7 flex flex-col gap-2.5">
          {STAGE_FULL.map((name, i) => {
            const no = i + 1;
            const st = stages[no];
            const status = st?.status || "pending";
            const r = st?.result;
            const isOpen = open[no] ?? false;
            return (
              <div key={no} className={`card transition-all flex flex-col flex-1 ${status === "running" ? "ring-2 ring-indigo/30" : ""} ${status === "pending" ? "opacity-60" : "pop"}`}>
                <button className="w-full flex-1 flex items-center gap-3 px-4 py-3 text-left" disabled={!r} onClick={() => setOpen({ ...open, [no]: !isOpen })}>
                  <StatusDot s={status} size={26} />
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-[14px]">{no} · {name}{status === "running" && <span className="ml-2 text-[12px] font-medium text-indigo">working…</span>}</div>
                    <div className="text-[12.5px] text-muted truncate">{r ? r.summary : STAGE_BLURB[i]}</div>
                  </div>
                  {r && <>
                    <span className={`text-[12px] font-semibold ${RESULT_TEXT[status]}`}>{RESULT_LABEL[status]}</span>
                    <span className="text-[12px] text-muted tabular-nums w-14 text-right">{ms(r.duration_ms)}</span>
                    {isOpen ? <ChevronDown size={16} className="text-muted" /> : <ChevronRight size={16} className="text-muted" />}
                  </>}
                </button>
                {r && isOpen && <StageBody no={no} r={r} res={res} />}
              </div>
            );
          })}
        </div>

        <div className="col-span-5 flex flex-col gap-4">
          {flash && <Banner tone={flash === "approve" ? "ok" : "warn"} icon={flash === "approve" ? <CheckCircle2 size={18} /> : <XCircle size={18} />} onClose={() => setFlash(null)}><b>Invoice {flash === "approve" ? "approved" : "rejected"}.</b> Your note is saved in the audit log.</Banner>}
          {!done ? (
            <div className="card p-6 text-center flex-1">
              <div className="text-[13px] text-muted mb-2">{finished ? "Saving the result…" : "Decision"}</div>
              <div className="text-[15px] font-semibold">{started ? "Working through the stages…" : "Waiting to start"}</div>
              <div className="h-1.5 rounded-full bg-line mt-4 overflow-hidden"><div className="h-full bg-indigo transition-all" style={{ width: `${(Object.values(stages).filter((s) => !["running", "pending"].includes(s.status)).length / 9) * 100}%` }} /></div>
            </div>
          ) : <DecisionCard id={id!} done={done} detail={detail.data} onOverride={setModal} />}
        </div>
      </div>
      {modal && <OverrideModal id={id!} action={modal} onClose={() => setModal(null)} onDone={(a) => { setModal(null); setFlash(a); setTimeout(() => setFlash(null), 6000); }} />}
    </div>
  );
}

function StageBody({ no, r, res }: { no: number; r: any; res: any }) {
  return (
    <div className="px-4 pb-4 border-t border-line">
      <table className="w-full text-[12.5px] mt-1">
        <thead><tr><th className="th w-14">Rule</th><th className="th">Check</th><th className="th w-16">Result</th><th className="th">Detail</th></tr></thead>
        <tbody>
          {r.checks.map((c: any, i: number) => (
            <tr key={i}>
              <td className="td font-mono text-[11.5px] text-muted">{c.rule}</td><td className="td font-medium">{c.label}</td>
              <td className={`td font-semibold ${RESULT_TEXT[c.result]}`}>{RESULT_LABEL[c.result]}</td><td className="td text-body">{c.detail}</td>
            </tr>
          ))}
          {!r.checks.length && <tr><td className="td text-muted" colSpan={4}>No individual checks for this stage.</td></tr>}
        </tbody>
      </table>
      {no === 2 && res?.extraction && <ExtractedPanel ex={res.extraction} />}
      {no === 6 && r.data?.candidates?.length > 0 && <Candidates data={r.data} />}
      {no === 7 && r.data?.po_net != null && <Ledger n={r.data} />}
    </div>
  );
}

function ExtractedPanel({ ex }: { ex: any }) {
  const F = ex.fields, C = ex.confidence;
  const rows: [string, string][] = [["Invoice number", "invoice_number"], ["Invoice date", "invoice_date"], ["Vendor", "vendor_name"], ["Vendor GSTIN", "vendor_gstin"],
    ["PO reference", "po_reference"], ["Subtotal", "subtotal"], ["Tax", "tax_total"], ["Total amount", "total_amount"]];
  const fmt = (k: string, v: any) => v == null ? <span className="text-bad font-medium">not found</span> : ["subtotal", "tax_total", "total_amount"].includes(k) ? inr(v) : String(v);
  return (
    <div className="mt-3 grid grid-cols-2 gap-4">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-muted font-semibold mb-1">Extracted fields · {ex.source === "text_pdf" ? "text layer" : "OCR of scanned image"}</div>
        <table className="w-full text-[12.5px]"><tbody>
          {rows.map(([l, k]) => <tr key={k}><td className="py-1 text-muted w-28">{l}</td><td className="py-1 font-medium">{fmt(k, F[k])}</td><td className="py-1"><ConfBar v={C[k] || 0} /></td></tr>)}
        </tbody></table>
      </div>
      <div>
        <div className="text-[11px] uppercase tracking-wide text-muted font-semibold mb-1">Line items and tax</div>
        <table className="w-full text-[12px]"><thead><tr><th className="th">Item</th><th className="th text-right">Qty</th><th className="th text-right">Amount</th></tr></thead><tbody>
          {ex.line_items.map((l: any, i: number) => <tr key={i}><td className="td !py-1.5">{l.description}</td><td className="td !py-1.5 text-right">{l.quantity}</td><td className="td !py-1.5 text-right">{inr(l.amount)}</td></tr>)}
          {ex.tax_lines.map((t: any, i: number) => <tr key={"t" + i}><td className="td !py-1.5 text-muted" colSpan={2}>{t.type} @ {t.rate}%</td><td className="td !py-1.5 text-right">{inr(t.amount)}</td></tr>)}
        </tbody></table>
      </div>
    </div>
  );
}

function Candidates({ data }: { data: any }) {
  return (
    <div className="mt-3">
      <div className="text-[11px] uppercase tracking-wide text-muted font-semibold mb-1">PO candidates · confidence = 0.35 amount + 0.35 description + 0.20 lines + 0.10 timing</div>
      {data.candidates.map((c: any) => (
        <div key={c.po_number} className={`flex items-center gap-3 py-1.5 text-[12.5px] ${c.po_number === data.matched_po ? "font-semibold" : ""}`}>
          <span className="w-28">{c.po_number}</span><span className="w-52 truncate text-muted">{c.po_description}</span>
          <div className="flex-1 h-2 bg-line rounded-full overflow-hidden"><div className="h-full" style={{ width: `${c.confidence * 100}%`, background: c.po_number === data.matched_po ? "#3B5BDB" : "#B8C2D6" }} /></div>
          <span className="w-10 text-right tabular-nums">{c.confidence.toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

function Ledger({ n }: { n: any }) {
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / n.po_net) * 100))}%`;
  return (
    <div className="mt-3">
      <div className="text-[11px] uppercase tracking-wide text-muted font-semibold mb-1">PO ledger</div>
      <div className="h-5 rounded-md bg-line overflow-hidden flex text-[10px] text-white font-semibold">
        <div className="bg-[#8A94A6] flex items-center justify-center" style={{ width: pct(n.billed_before) }}>{n.billed_before > 0 && "billed"}</div>
        <div className={n.overrun_pct > 2 ? "bg-bad flex items-center justify-center" : "bg-indigo flex items-center justify-center"} style={{ width: pct(Math.min(n.invoice_subtotal, n.po_net - n.billed_before)) }}>this</div>
      </div>
      <div className="flex justify-between text-[12px] text-muted mt-1"><span>PO {inr(n.po_net, 0)}</span><span>Remaining after: <b className={n.remaining_after < 0 ? "text-bad" : "text-ink"}>{inr(n.remaining_after, 0)}</b></span></div>
    </div>
  );
}

function DecisionCard({ id, done, detail, onOverride }: { id: string; done: any; detail: any; onOverride: (a: "approve" | "reject") => void }) {
  const d = detail?.result?.decision;
  const v = detail?.final_decision || done.decision;
  const overridden = detail && detail.final_decision !== detail.decision;
  const col = VERDICT[v]?.bar || "#3B5BDB";
  const F = detail?.result?.extraction?.fields || {};
  const num = detail?.result?.numeric || {};
  const facts: [string, string][] = [["Invoice total", inr(F.total_amount)], ["Matched PO", detail?.po_number || "—"],
    ["PO balance after", num.remaining_after != null ? inr(num.remaining_after, 0) : "—"], ["Confidence", detail?.confidence ? `${Math.round(detail.confidence * 100)}%` : "—"]];
  return (
    <div className="card overflow-hidden pop flex-1" style={{ borderTop: `4px solid ${col}` }}>
      <div className="p-5">
        <div className="flex items-center justify-between"><VerdictBadge v={v} big />{done.top_rule && <span className="font-mono text-[12px] bg-bg rounded px-2 py-1 text-muted">{done.top_rule}</span>}</div>
        {overridden && (() => { const o = detail.overrides?.[detail.overrides.length - 1]; const ap = detail.final_decision === "Approve";
          return <div className={`mt-3 rounded-lg border px-3 py-2.5 text-[13px] ${ap ? "bg-ok-soft border-ok/30" : "bg-bad-soft border-bad/30"}`}>
            <div className={`flex items-center gap-2 font-semibold ${ap ? "text-ok" : "text-bad"}`}>{ap ? <CheckCircle2 size={16} /> : <XCircle size={16} />}{ap ? "Approved" : "Rejected"} by {o?.user || "reviewer"}{o?.ts ? ` on ${new Date(o.ts).toLocaleString()}` : ""}</div>
            <div className="text-body mt-1">Pipeline said <b>{detail.decision}</b>; a person changed it to <b>{detail.final_decision}</b>.{o?.note ? <> Reason: “{o.note}”</> : null}</div>
          </div>; })()}
        <p className="mt-3 text-[13.5px] leading-relaxed">{detail?.reason || done.reason}</p>
        <div className="mt-1 text-[11px] text-muted">Reason source: rule templates (numbers pulled from the checks)</div>
        <div className="grid grid-cols-2 gap-2 mt-4">
          {facts.map(([l, val]) => <div key={l} className="rounded-lg bg-bg px-3 py-2"><div className="text-[10.5px] uppercase tracking-wide text-muted font-semibold">{l}</div><div className="font-semibold text-[14px] truncate">{l === "Matched PO" && val !== "—" ? <Link className="text-indigo hover:underline" to={`/deepdive?type=po&id=${val}`} title="Open PO balance view">{val} →</Link> : val}</div></div>)}
        </div>
        {d?.what_to_check?.length > 0 && (
          <div className="mt-4"><div className="text-[11px] uppercase tracking-wide text-muted font-semibold mb-1">What to check</div>
            <ul className="space-y-1">{d.what_to_check.map((w: any, i: number) => <li key={i} className="flex gap-2 text-[13px]"><ShieldCheck size={15} className="text-warn mt-0.5 shrink-0" /><span>{w.action} <span className="text-muted font-mono text-[11px]">{w.rule}</span></span></li>)}</ul></div>
        )}
        {d?.trail?.length > 0 && (
          <div className="mt-4"><div className="text-[11px] uppercase tracking-wide text-muted font-semibold mb-1">Rule trail</div>
            <div className="space-y-1.5">{d.trail.map((t: any, i: number) => (
              <div key={i} className="flex gap-2 text-[12.5px]"><span className={`chip !py-0 !px-1.5 text-[10.5px] shrink-0 self-start whitespace-nowrap ${LEVEL_CHIP[t.level]}`}>{t.level}</span><span className="font-mono text-[11px] text-muted shrink-0 mt-0.5">{t.rule}</span><span className="text-body">{t.detail}</span></div>))}</div></div>
        )}
        <div className="mt-4 text-[13px]"><span className="text-muted">Next action: </span><b>{d?.next_action}</b></div>
        <div className="flex flex-wrap gap-2 mt-4">
          {detail?.decision === "Review" && detail?.final_decision === "Review" && <>
            <button className="btn-primary !bg-ok hover:!bg-[#17814A]" onClick={() => onOverride("approve")}>Approve</button>
            <button className="btn-primary !bg-bad hover:!bg-[#B83A3A]" onClick={() => onOverride("reject")}>Reject</button></>}
          <a className="btn-ghost" href={`/api/runs/${id}/report.pdf`}><Download size={14} />Run report PDF</a>
          {d?.vendor_message && <a className="btn-ghost" href={`/api/runs/${id}/vendor-letter.pdf`}><Mail size={14} />Vendor letter PDF</a>}
        </div>
        {d?.vendor_message && <details className="mt-3"><summary className="text-[12px] text-indigo cursor-pointer font-medium">Preview vendor message</summary><pre className="mt-2 whitespace-pre-wrap text-[12px] bg-bg rounded-lg p-3 font-sans">{d.vendor_message}</pre></details>}
      </div>
    </div>
  );
}

function OverrideModal({ id, action, onClose, onDone }: { id: string; action: string; onClose: () => void; onDone: (a: string) => void }) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const MIN = 10;
  const len = note.trim().length;
  const ready = len >= MIN;
  const m = useMutation({ mutationFn: () => post(`/runs/${id}/override`, { action, note }), onSuccess: () => { qc.invalidateQueries(); onDone(action); } });
  const color = action === "approve" ? "!bg-ok hover:!bg-[#17814A]" : "!bg-bad hover:!bg-[#B83A3A]";
  return (
    <Modal title={`${action === "approve" ? "Approve" : "Reject"} this Review item`} onClose={onClose}>
      <p className="text-[13px] text-muted mb-3">A note is required so the audit log records why a person overruled the Review verdict.</p>
      <textarea autoFocus className="input h-24" placeholder="Reason for the decision (at least 10 characters)" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className={`text-[12px] mt-1.5 ${ready ? "text-ok font-semibold" : "text-muted"}`}>{ready ? `✓ Note is long enough (${len} characters)` : `Write at least ${MIN} characters`}</div>
      {m.error && <div className="text-bad text-[12px] mt-2">{(m.error as Error).message}</div>}
      <div className="flex justify-end gap-2 mt-4"><button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className={`btn-primary ${ready ? color : "!bg-line !text-muted cursor-not-allowed"}`} disabled={!ready || m.isPending} onClick={() => m.mutate()}>{m.isPending ? "Saving…" : `Confirm ${action}`}</button></div>
    </Modal>
  );
}
