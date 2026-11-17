import { useQuery } from "@tanstack/react-query";
import { Download, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Empty, Section, VerdictBadge } from "../components/ui";
import { ago, inr, ms } from "../lib";

export default function HistoryPage() {
  const [f, setF] = useState(""); const [q, setQ] = useState("");
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api("/runs"), refetchInterval: 4000 });
  const rows = (runs.data || []).filter((r: any) => (!f || (r.final_decision || r.decision) === f) && (!q || [r.filename, r.vendor_name, r.invoice_number, r.po_number].join(" ").toLowerCase().includes(q.toLowerCase())));
  return (
    <Section title={`${rows.length} run${rows.length === 1 ? "" : "s"}`} right={
      <div className="flex items-center gap-2">
        {["", "Approve", "Review", "Reject"].map((k) => <button key={k} onClick={() => setF(k)} className={`chip border ${f === k ? "bg-indigo text-white border-indigo" : "bg-surface border-line text-ink"}`}>{k || "All"}</button>)}
        <div className="relative"><Search size={14} className="absolute left-2.5 top-2.5 text-muted" /><input className="input !pl-8 !w-52" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <a className="btn-ghost !py-1.5" href="/api/runs/export.csv"><Download size={13} />Export CSV</a>
      </div>}>
      {!rows.length ? <Empty title="No runs match" /> :
        <table className="w-full text-[13px]"><thead><tr><th className="th">File</th><th className="th">Vendor</th><th className="th">Invoice no.</th><th className="th">PO</th><th className="th text-right">Total</th><th className="th">Decision</th><th className="th">Rule</th><th className="th text-right">Time</th><th className="th">When</th></tr></thead>
          <tbody>{rows.map((r: any) => <tr key={r.run_id} className="hover:bg-bg">
            <td className="td"><Link className="text-indigo font-medium" to={`/run/${r.run_id}`}>{r.filename}</Link></td><td className="td">{r.vendor_name || "—"}</td><td className="td">{r.invoice_number || "—"}</td>
            <td className="td font-mono text-[12px]">{r.po_number || "—"}</td><td className="td text-right tabular-nums">{inr(r.total)}</td>
            <td className="td"><VerdictBadge v={r.final_decision || r.decision} />{r.final_decision !== r.decision && <span className="ml-1 text-[11px] text-ai">overridden</span>}</td>
            <td className="td font-mono text-[12px] text-muted">{r.top_rule || "—"}</td><td className="td text-right text-muted">{ms(r.total_ms)}</td><td className="td text-muted">{ago(r.started_at)}</td></tr>)}</tbody></table>}
    </Section>
  );
}
