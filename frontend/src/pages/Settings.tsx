import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Check, Copy, Cpu, FileSearch, RotateCcw, Save, Scale, Timer } from "lucide-react";
import { ReactNode, useEffect, useState } from "react";
import { api, post, put } from "../api";
import { Collapsible, Section } from "../components/ui";
import { STAGE_FULL } from "../lib";

type F = { k: string; label: string; min: number; max: number; step: number; unit: string; def: number; hint: string };
const CARDS: { title: string; sub: string; icon: ReactNode; color: string; fields: F[] }[] = [
  { title: "Price tolerance", sub: "How far over the PO an invoice may go", icon: <Scale size={16} />, color: "#3B5BDB", fields: [
    { k: "price_tolerance_auto_pct", label: "Auto-approve tolerance", min: 0, max: 10, step: 0.5, unit: "%", def: 2, hint: "Up to this much over the PO can still be auto-approved" },
    { k: "price_tolerance_review_pct", label: "Review tolerance", min: 1, max: 25, step: 0.5, unit: "%", def: 10, hint: "Above this the invoice is rejected; between the two it goes to Review" }] },
  { title: "Duplicates & vendor match", sub: "Catch re-sends and look-alike names", icon: <Copy size={16} />, color: "#D64545", fields: [
    { k: "duplicate_window_days", label: "Duplicate window", min: 7, max: 365, step: 1, unit: "days", def: 90, hint: "Same vendor and amount within this window is a probable duplicate" },
    { k: "vendor_name_match", label: "Vendor name match score", min: 70, max: 100, step: 1, unit: "", def: 92, hint: "Fuzzy score needed to treat a name as the same vendor" }] },
  { title: "Extraction & limits", sub: "What may be approved without a person", icon: <FileSearch size={16} />, color: "#1F9D55", fields: [
    { k: "min_confidence_critical", label: "Min. confidence on critical fields", min: 0.5, max: 0.99, step: 0.01, unit: "", def: 0.8, hint: "Below this a field can never lead to auto-approval" },
    { k: "auto_approve_max_amount_inr", label: "High-value limit", min: 50000, max: 5000000, step: 50000, unit: "₹", def: 500000, hint: "Larger invoices always get a human" },
    { k: "gst_tolerance_inr", label: "GST rounding tolerance", min: 0, max: 10, step: 0.5, unit: "₹", def: 1, hint: "Allowed difference in tax and total arithmetic" }] },
  { title: "PO inference", sub: "When no PO number is printed", icon: <Cpu size={16} />, color: "#7048E8", fields: [
    { k: "po_infer_min", label: "Minimum confidence", min: 0.5, max: 0.99, step: 0.01, unit: "", def: 0.75, hint: "Needed to infer a PO that is not printed" },
    { k: "po_infer_margin", label: "Lead over runner-up", min: 0.05, max: 0.5, step: 0.01, unit: "", def: 0.15, hint: "Gap the best PO must have over the second best" }] },
  { title: "Live demo", sub: "Presentation helpers", icon: <Timer size={16} />, color: "#D98A00", fields: [
    { k: "ui_pacing_ms", label: "Pacing per stage", min: 0, max: 1500, step: 50, unit: "ms", def: 600, hint: "Slows the run slightly so each stage is visible in a demo" }] },
];
const LEVEL: Record<string, string> = { REJECT: "bg-bad-soft text-bad", REVIEW: "bg-warn-soft text-warn", INFO: "bg-bg text-muted" };

export default function SettingsPage() {
  const qc = useQueryClient();
  const cfg = useQuery({ queryKey: ["config"], queryFn: () => api("/config") });
  const rules = useQuery({ queryKey: ["rules"], queryFn: () => api("/rules") });
  const gd = useQuery({ queryKey: ["guide"], queryFn: () => api("/guide"), refetchInterval: 10000 });
  const [draft, setDraft] = useState<any>({});
  const [saved, setSaved] = useState(false);
  useEffect(() => { if (cfg.data) setDraft(cfg.data); }, [cfg.data]);
  const dirty = cfg.data && Object.keys(draft).some((k) => String(draft[k]) !== String(cfg.data[k]) && typeof cfg.data[k] !== "object");
  const save = useMutation({ mutationFn: () => put("/config", draft), onSuccess: () => { qc.invalidateQueries({ queryKey: ["config"] }); qc.invalidateQueries({ queryKey: ["guide"] }); qc.invalidateQueries({ queryKey: ["readiness"] }); setSaved(true); setTimeout(() => setSaved(false), 2000); } });
  const reset = useMutation({ mutationFn: () => post("/config/reset"), onSuccess: () => { qc.invalidateQueries({ queryKey: ["config"] }); qc.invalidateQueries({ queryKey: ["guide"] }); } });
  const byStage: Record<number, any[]> = {};
  (rules.data || []).forEach((r: any) => (byStage[r.stage] = byStage[r.stage] || []).push(r));
  const set = (k: string, v: string) => setDraft({ ...draft, [k]: v });
  return (
    <div className="space-y-5">
      <div className="card px-5 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3 text-[13px]"><BadgeCheck size={18} className="text-ok" /><span><b>Policy ACTIVE.</b> Changes apply to the next run immediately.</span>
          {dirty && <span className="chip !py-0 bg-warn-soft text-warn text-[11px]">unsaved changes</span>}</div>
        <div className="flex gap-2"><button className="btn-ghost !py-1.5" onClick={() => reset.mutate()}><RotateCcw size={13} />Defaults</button>
          <button className="btn-primary !py-1.5" onClick={() => save.mutate()}>{saved ? <><Check size={14} />Applied</> : <><Save size={14} />Save & apply</>}</button></div>
      </div>

      <div className="grid grid-cols-2 gap-5">
        {CARDS.map((c) => (
          <div key={c.title} className="card overflow-hidden" style={{ borderTop: `3px solid ${c.color}` }}>
            <div className="px-4 py-3 flex items-center gap-3 border-b border-line"><span className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: c.color + "1A", color: c.color }}>{c.icon}</span>
              <div><div className="font-semibold text-[14px] leading-tight">{c.title}</div><div className="text-[12px] text-muted">{c.sub}</div></div></div>
            <div className="p-4 space-y-5">{c.fields.map((f) => {
              const v = draft[f.k] ?? f.def; const changed = cfg.data && String(cfg.data[f.k]) !== String(v);
              return (
                <div key={f.k}>
                  <div className="flex items-center justify-between"><span className="text-[11px] tracking-[0.1em] uppercase font-bold text-body">{f.label}</span>
                    <span className="chip !py-0 text-[11px] bg-ok-soft text-ok">{changed ? "PENDING" : "ACTIVE"}: {f.unit === "₹" ? `₹${Number(cfg.data?.[f.k] ?? f.def).toLocaleString("en-IN")}` : `${cfg.data?.[f.k] ?? f.def}${f.unit && f.unit !== "" ? " " + f.unit : ""}`}</span></div>
                  <div className="flex items-center gap-3 mt-2">
                    <input type="range" min={f.min} max={f.max} step={f.step} value={v} onChange={(e) => set(f.k, e.target.value)} className="flex-1 accent-indigo" />
                    <div className="flex items-center gap-1"><input className="input !w-24 !py-1 text-right" type="number" step={f.step} value={v} onChange={(e) => set(f.k, e.target.value)} /><span className="text-[12px] text-muted w-8">{f.unit}</span></div></div>
                  <div className="text-[11.5px] text-muted mt-1">{f.hint} · range {f.min}–{f.max}</div>
                </div>);
            })}</div>
          </div>))}
        <div className="card p-4 text-[12.5px] text-body space-y-1.5">
          <div className="text-[11px] tracking-[0.1em] uppercase font-bold">Fixed settings</div>
          <div>Buyer: <b>{cfg.data?.buyer_name}</b></div><div>GSTIN: <span className="font-mono">{cfg.data?.buyer_gstin}</span> · state {cfg.data?.buyer_state}</div>
          <div>Critical fields: {(cfg.data?.critical_fields || []).join(", ")}</div><div>Limits: {cfg.data?.max_pages} pages · {cfg.data?.max_file_mb} MB · stale PO {cfg.data?.stale_days} days</div>
          <div>Text/scan switch: {cfg.data?.min_text_density} characters per page</div></div>
      </div>

      <div className="text-[11.5px] tracking-[0.12em] uppercase font-bold text-body pt-2">Reference guide</div>
      <Collapsible title="Pipeline stages · S1 to S9, owner and standard turnaround">
        <div className="grid grid-cols-2 gap-x-10 gap-y-2.5">{(gd.data?.stages || []).map((s: any) => (
          <div key={s.no} className="flex items-center gap-3 text-[13px]"><span className="w-9 text-center text-[11px] font-bold bg-indigo-soft text-indigo rounded py-0.5">S{s.no}</span><span className="font-semibold w-44">{STAGE_FULL[s.no - 1]}</span><span className="text-muted">{s.owner} · {s.std_tat_h} h</span></div>))}</div>
      </Collapsible>
      <Collapsible title="Formulas and decision logic">
        <div className="grid grid-cols-2 gap-5">{(gd.data?.formulas || []).map((f: any) => (
          <div key={f.id}><div className="text-[13.5px] font-bold">{f.title}</div><div className="text-[12.5px] text-body mt-1">{f.text}</div>
            <code className="block mt-1.5 text-[11.5px] bg-indigo-soft text-indigo-dark rounded px-2.5 py-1.5 font-mono leading-relaxed">{f.formula}</code></div>))}</div>
      </Collapsible>
      <Collapsible title="Rule table · every verdict traces to one of these ids" right={<span className="text-[12px] text-muted">{(rules.data || []).length} rules</span>}>
        <div className="-mx-4 -mb-4">
        <table className="w-full text-[13px]"><thead><tr><th className="th w-16">Rule</th><th className="th w-40">Stage</th><th className="th w-56">Name</th><th className="th">What it checks</th><th className="th w-24">On warn</th><th className="th w-24">On fail</th></tr></thead>
          <tbody>{Object.entries(byStage).flatMap(([s, rs]) => rs.map((r: any) => <tr key={r.id}>
            <td className="td font-mono text-[12px]">{r.id}</td><td className="td text-muted">{s} · {STAGE_FULL[+s - 1]}</td><td className="td font-medium">{r.name}</td><td className="td text-body">{r.description}</td>
            <td className="td">{r.warn && <span className={`chip !py-0 ${LEVEL[r.warn]}`}>{r.warn}</span>}</td><td className="td">{r.fail && <span className={`chip !py-0 ${LEVEL[r.fail]}`}>{r.fail}</span>}</td></tr>))}</tbody></table>
        </div>
      </Collapsible>
    </div>
  );
}
