import { useQuery } from "@tanstack/react-query";
import { CircleCheck, Database, Download, FileUp, Sparkles } from "lucide-react";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, uploadFile } from "../api";
import { Banner, Section, VerdictBadge } from "../components/ui";
import { ago } from "../lib";

export default function UploadPage() {
  const nav = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [banner, setBanner] = useState(true);
  const samples = useQuery({ queryKey: ["samples"], queryFn: () => api("/samples") });
  const sm: any[] = samples.data || [];
  const cfg = useQuery({ queryKey: ["config"], queryFn: () => api("/config") });
  const rd = useQuery({ queryKey: ["readiness"], queryFn: () => api("/readiness"), refetchInterval: 8000 });
  const an = useQuery({ queryKey: ["analytics", ""], queryFn: () => api("/analytics") });
  const r = rd.data;
  const cnt = (code: string) => (r?.cards || []).find((c: any) => c.code === code)?.rows;
  const last = an.data?.last_run;

  const go = async (files: FileList | File[]) => {
    setErr("");
    const list = Array.from(files);
    if (!list.length) return;
    setBusy(true);
    try {
      let first = "";
      for (const f of list) {
        if (!f.name.toLowerCase().endsWith(".pdf")) throw new Error(`${f.name}: PDF only`);
        const id = await uploadFile(f);
        if (!first) first = id;
      }
      nav(`/run/${first}`);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      {banner && last && (
        <Banner tone="ok" icon={<CircleCheck size={16} />} onClose={() => setBanner(false)}>
          <b>InvoiceIQ last ran {ago(last.at)}</b> on {last.invoice_number || last.filename} → <b>{last.decision}</b>. Your earlier runs are kept: see the <Link to="/dashboard" className="underline font-semibold">Dashboard</Link> or <Link to="/history" className="underline font-semibold">Run History</Link>.
        </Banner>
      )}

      <div className="grid grid-cols-5 gap-5 items-stretch">
        <div className="col-span-3">
          <div
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); go(e.dataTransfer.files); }}
            onClick={() => input.current?.click()}
            className={`h-full min-h-[320px] flex flex-col items-center justify-center cursor-pointer rounded-2xl border-2 border-dashed px-8 py-12 text-center transition-colors ${drag ? "border-indigo bg-indigo-soft" : "border-line2 bg-surface hover:border-indigo"}`}>
            <div className="mx-auto w-14 h-14 rounded-full bg-indigo-soft text-indigo flex items-center justify-center mb-4"><FileUp size={26} /></div>
            <div className="text-[18px] font-semibold">Drop an invoice PDF or click to browse</div>
            <div className="text-[13px] text-muted mt-1">One PDF per run · up to {cfg.data?.max_file_mb ?? 10} MB · scans supported</div>
            {busy && <div className="mt-3 text-indigo text-[13px] font-medium">Uploading…</div>}
            {err && <div className="mt-3 text-bad text-[13px] font-medium">{err}</div>}
            <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden onChange={(e) => e.target.files && go(e.target.files)} />
          </div>
        </div>
        <div className="col-span-2">
          <Section title="Sample invoices" className="h-full flex flex-col" right={<span className="chip bg-ai-soft text-ai"><Sparkles size={12} />{sm.length || 10} test files</span>}>
            <div className="p-5 flex-1 flex flex-col justify-between gap-4">
              <div className="space-y-3">
                <p className="text-[13px] text-body">No invoice handy? Download ready-made ones that cover the main situations: a clean match, price difference, split PO, duplicate, scanned copy, blocked vendor, closed PO and wrong tax.</p>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-[12px]">
                  <span className="text-muted">Expected verdicts:</span>
                  {(["Approve", "Review", "Reject"] as const).map((v) => <span key={v} className="inline-flex items-center gap-1.5"><VerdictBadge v={v} /><b>{sm.filter((x: any) => x.expected === v).length}</b></span>)}
                </div>
                <p className="text-[12.5px] text-muted">A README inside lists what each file tests and the verdict to expect.</p>
              </div>
              <div className="space-y-2">
                <a href="/api/samples.zip" download className="btn-primary w-full justify-center"><Download size={15} />Download sample invoices (.zip)</a>
                <p className="text-[12px] text-muted">Upload one at a time. Run <b>S03</b> before <b>S04</b>, as the PO balance has to fall first.</p>
              </div>
            </div>
          </Section>
        </div>
      </div>

      <Section title="What happens next">
        <div className="p-5 grid grid-cols-3 gap-6 text-[13px]">
          {[["1", "Read", "Text layer or OCR turns the PDF into fields, with a confidence score for each."],
            ["2", "Check", "Rules test the vendor, duplicates, PO match, GST and price tolerance."],
            ["3", "Decide", "Approve, Review or Reject, with the rule that fired and a plain-English reason."]].map(([n, t, d]) => (
            <div key={n} className="flex gap-3"><div className="w-6 h-6 rounded-full bg-indigo text-white text-[12px] font-bold flex items-center justify-center shrink-0">{n}</div><div><div className="font-semibold">{t}</div><div className="text-muted mt-0.5">{d}</div></div></div>
          ))}
        </div>
      </Section>

      {r && (
        <div className="card px-5 py-3 flex items-center gap-3 text-[13px]">
          <Database size={16} className="text-muted shrink-0" />
          <span className="text-body">Checked against your reference data: <b>{cnt("VM") ?? "—"}</b> vendors · <b>{cnt("PO") ?? "—"}</b> POs · <b>{cnt("IH") ?? "—"}</b> past invoices · <b>{cnt("RT") ?? "—"}</b> rules</span>
          <Link to="/data" className="ml-auto text-indigo font-semibold">View in Reference Data →</Link>
        </div>
      )}
    </div>
  );
}
