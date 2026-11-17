import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Building2, FileStack, Receipt, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, post } from "../api";
import { Kpi, Section } from "../components/ui";
import { inr } from "../lib";

export default function Data() {
  const qc = useQueryClient();
  const [sp] = useSearchParams();
  const [tab, setTab] = useState(sp.get("tab") || "pos");
  const v = useQuery({ queryKey: ["vendors"], queryFn: () => api("/vendors") });
  const p = useQuery({ queryKey: ["pos"], queryFn: () => api("/pos"), refetchInterval: 4000 });
  const i = useQuery({ queryKey: ["invoices"], queryFn: () => api("/invoices"), refetchInterval: 4000 });
  const reset = useMutation({ mutationFn: () => post("/reset"), onSuccess: () => qc.invalidateQueries() });
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-4">
        <Kpi label="Vendors" value={v.data?.length ?? "—"} icon={<Building2 size={14} />} sub={`${(v.data || []).filter((x: any) => x.approval_status !== "Approved").length} blocked`} />
        <Kpi label="Purchase orders" value={p.data?.length ?? "—"} color="#7048E8" icon={<FileStack size={14} />} sub={`${(p.data || []).filter((x: any) => x.status === "Open").length} open`} />
        <Kpi label="Invoices on record" value={i.data?.length ?? "—"} color="#1F9D55" icon={<Receipt size={14} />} sub="history plus processed" />
        <div className="card p-4 flex flex-col justify-between" style={{ borderTop: "3px solid #D64545" }}>
          <div className="text-[11px] uppercase tracking-wide font-semibold text-muted">Demo data</div>
          <button className="btn-ghost justify-center mt-2" onClick={() => confirm("Clear all runs and reload the seed data?") && reset.mutate()}><RotateCcw size={14} />Reset demo data</button>
        </div>
      </div>
      <div className="flex gap-2">{[["pos", "Purchase orders"], ["vendors", "Vendors"], ["invoices", "Invoices"]].map(([k, l]) => <button key={k} onClick={() => setTab(k)} className={`chip border ${tab === k ? "bg-indigo text-white border-indigo" : "bg-surface border-line"}`}>{l}</button>)}</div>
      <Section title={tab === "pos" ? "Purchase orders and billed balance" : tab === "vendors" ? "Vendor master" : "Invoice register"}>
        {tab === "pos" && <table className="w-full text-[13px]"><thead><tr><th className="th">PO</th><th className="th">Vendor</th><th className="th">Description</th><th className="th">Status</th><th className="th text-right">Net</th><th className="th text-right">Billed</th><th className="th text-right">Remaining</th><th className="th w-40">Utilisation</th></tr></thead>
          <tbody>{(p.data || []).map((x: any) => <tr key={x.po_number}><td className="td font-mono text-[12px]"><Link className="text-indigo font-medium" to={`/deepdive?type=po&id=${x.po_number}`}>{x.po_number}</Link></td><td className="td">{x.vendor_id}</td><td className="td">{x.description}</td>
            <td className="td"><span className={`chip ${x.status === "Open" ? "bg-ok-soft text-ok" : "bg-bg text-muted"}`}>{x.status}</span></td><td className="td text-right tabular-nums">{inr(x.net_amount, 0)}</td><td className="td text-right tabular-nums">{inr(x.billed, 0)}</td>
            <td className="td text-right tabular-nums font-semibold">{inr(x.remaining, 0)}</td><td className="td"><div className="h-2 rounded-full bg-line overflow-hidden"><div className="h-full bg-indigo" style={{ width: `${Math.min(100, (x.billed / x.net_amount) * 100)}%` }} /></div></td></tr>)}</tbody></table>}
        {tab === "vendors" && <table className="w-full text-[13px]"><thead><tr><th className="th">ID</th><th className="th">Legal name</th><th className="th">GSTIN</th><th className="th">State</th><th className="th">Bank account</th><th className="th">IFSC</th><th className="th">Status</th></tr></thead>
          <tbody>{(v.data || []).map((x: any) => <tr key={x.vendor_id}><td className="td font-mono text-[12px]">{x.vendor_id}</td><td className="td font-medium">{x.legal_name}</td><td className="td font-mono text-[12px]">{x.gstin}</td><td className="td">{x.state_code}</td><td className="td font-mono text-[12px]">{x.bank_account_no}</td><td className="td font-mono text-[12px]">{x.ifsc}</td>
            <td className="td"><span className={`chip ${x.approval_status === "Approved" ? "bg-ok-soft text-ok" : "bg-bad-soft text-bad"}`}>{x.approval_status}</span></td></tr>)}</tbody></table>}
        {tab === "invoices" && <table className="w-full text-[13px]"><thead><tr><th className="th">Invoice no.</th><th className="th">Vendor</th><th className="th">Date</th><th className="th">PO</th><th className="th text-right">Subtotal</th><th className="th text-right">Total</th><th className="th">Decision</th><th className="th">Source</th></tr></thead>
          <tbody>{(i.data || []).map((x: any, k: number) => <tr key={k}><td className="td">{x.invoice_number || "—"}</td><td className="td">{x.vendor_id}</td><td className="td">{x.invoice_date}</td><td className="td font-mono text-[12px]">{x.po_number || "—"}</td><td className="td text-right tabular-nums">{inr(x.subtotal)}</td><td className="td text-right tabular-nums">{inr(x.total)}</td><td className="td">{x.decision}</td><td className="td text-muted">{x.source}</td></tr>)}</tbody></table>}
      </Section>
    </div>
  );
}
