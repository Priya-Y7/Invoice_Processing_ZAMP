import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, FileStack } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { Banner, ChartTip, Ring, Section, VerdictBadge } from "../components/ui";
import { CH, inr, inrShort } from "../lib";
import { useChartColors } from "../theme";


function PoView({ id }: { id: string }) {
  const cc = useChartColors();
  const AX = { fontSize: 11, fill: cc.axis };
  const q = useQuery({ queryKey: ["poprofile", id], queryFn: () => api(`/pos/${id}/profile`), refetchInterval: 5000 });
  const d = q.data;
  if (!d) return null;
  const p = d.po;
  const wf: any[] = [{ name: "PO net", base: 0, value: p.net, c: CH.purple }];
  let bal = p.net;
  d.steps.filter((s: any) => s.counted).forEach((s: any) => { bal -= s.subtotal; wf.push({ name: s.invoice_number, base: Math.max(0, bal), value: Math.min(s.subtotal, s.subtotal + Math.min(0, bal)), c: CH.teal }); });
  wf.push({ name: "Remaining", base: 0, value: Math.max(0, bal), c: bal < 0 ? CH.red : CH.green });
  const over = d.steps.find((s: any) => s.overrun_pct > 0);
  return (
    <div className="space-y-5">
      <div className="card p-5 flex items-center gap-5">
        <span className="w-12 h-12 rounded-xl bg-ai-soft text-ai flex items-center justify-center"><FileStack size={22} /></span>
        <div className="flex-1"><div className="text-[18px] font-bold font-mono">{p.po_number}</div><div className="text-[13px] text-muted">{p.description} · {p.vendor_name} · issued {p.issue_date}</div></div>
        <span className={`chip ${p.status === "Open" ? "bg-ok-soft text-ok" : "bg-bg text-muted"}`}>{p.status}</span>
      </div>
      <div className="grid grid-cols-12 gap-5">
        <Section title="PO position" className="col-span-5">
          <div className="p-5 flex items-center gap-6">
            <Ring value={Math.min(100, Math.round(p.utilisation_pct))} label="Utilised" />
            <dl className="flex-1 text-[13px] space-y-2">{[["PO net (ex-GST)", p.net], ["Billed (approved)", p.billed]].map(([k, v]: any) => <div key={k} className="flex justify-between"><dt className="text-muted">{k}</dt><dd className="font-semibold tabular-nums">{inr(v, 0)}</dd></div>)}
              <div className="flex justify-between border-t border-line pt-2"><dt className="font-semibold">Remaining</dt><dd className={`font-bold tabular-nums ${p.remaining <= 0 ? "text-bad" : ""}`}>{inr(p.remaining, 0)}</dd></div>
              <div className="flex justify-between text-[12px]"><dt className="text-muted">GST rate</dt><dd>{p.gst_rate_pct}%</dd></div></dl>
          </div>
          {over && <div className="px-4 pb-4"><Banner tone="warn" icon={<AlertTriangle size={15} />}>An invoice pushed this PO {over.overrun_pct}% over its value. Tolerance: {`up to 2% passes, up to 10% goes to Review, above that is rejected.`}</Banner></div>}
        </Section>
        <Section title="Balance waterfall" className="col-span-7">
          <div className="h-[250px] p-2"><ResponsiveContainer><BarChart data={wf} margin={{ top: 10 }}><XAxis dataKey="name" tick={{ ...AX, fontSize: 10 }} interval={0} axisLine={false} tickLine={false} /><YAxis hide />
            <Tooltip content={<ChartTip fmt={(v: any) => inr(v, 0)} />} cursor={cc.cursor} /><Bar dataKey="base" name="base" stackId="a" fill="transparent" isAnimationActive={false} />
            <Bar dataKey="value" name="Amount" stackId="a" barSize={46} radius={[5, 5, 0, 0]} activeBar={{ fillOpacity: 0.78 }}>{wf.map((x, i) => <Cell key={i} fill={x.c} />)}</Bar></BarChart></ResponsiveContainer></div>
        </Section>
      </div>
      <div className="grid grid-cols-12 gap-5">
        <Section title="Invoices against this PO" className="col-span-7">
          {d.steps.length ? <table className="w-full text-[13px]"><thead><tr><th className="th">Invoice</th><th className="th">Date</th><th className="th text-right">Subtotal</th><th className="th">Decision</th><th className="th text-right">Balance after</th></tr></thead>
            <tbody>{d.steps.map((s: any, i: number) => <tr key={i} className="hover:bg-bg"><td className="td">{s.run_id ? <Link className="text-indigo font-medium" to={`/run/${s.run_id}`}>{s.invoice_number}</Link> : s.invoice_number}</td><td className="td">{s.date}</td><td className="td text-right tabular-nums">{inr(s.subtotal, 0)}</td>
              <td className="td">{s.decision ? <VerdictBadge v={s.decision} /> : "—"}{!s.counted && <span className="ml-1 text-[11px] text-muted">not counted</span>}</td><td className={`td text-right tabular-nums ${s.balance_after < 0 ? "text-bad font-semibold" : ""}`}>{inr(s.balance_after, 0)}</td></tr>)}</tbody></table>
            : <div className="p-8 text-center text-[13px] text-muted">No invoice has been recorded against this PO.</div>}
        </Section>
        <Section title="PO lines" className="col-span-5">
          <table className="w-full text-[13px]"><thead><tr><th className="th">Line</th><th className="th text-right">Qty</th><th className="th text-right">Unit</th><th className="th text-right">Amount</th></tr></thead>
            <tbody>{d.lines.map((l: any) => <tr key={l.line_no}><td className="td">{l.description}</td><td className="td text-right tabular-nums">{l.quantity}</td><td className="td text-right tabular-nums">{inr(l.unit_price, 0)}</td><td className="td text-right tabular-nums">{inr(l.amount, 0)}</td></tr>)}</tbody></table>
        </Section>
      </div>
    </div>
  );
}

export default function DeepDive() {
  const [sp, setSp] = useSearchParams();
  const lk = useQuery({ queryKey: ["lookups"], queryFn: () => api("/lookups") });
  const list = lk.data?.pos || [];
  const id = sp.get("id") || list[0]?.id || "";
  useEffect(() => { if (!sp.get("id") && list[0]) setSp({ type: "po", id: list[0].id }, { replace: true }); }, [list.length]);
  return (
    <div className="space-y-5">
      <div className="card px-4 py-3 flex items-end gap-4">
        <label className="flex-1 max-w-md"><span className="text-[10.5px] uppercase tracking-wide font-semibold text-muted">Purchase order</span>
          <select className="input !py-1.5 mt-1" value={id} onChange={(e) => setSp({ type: "po", id: e.target.value })}>{list.map((x: any) => <option key={x.id} value={x.id}>{x.id} — {x.name}</option>)}</select></label>
        <div className="text-[12.5px] text-muted pb-2">Shows how each invoice draws the PO down. This is what the split-PO edge case (S03, S04) is checked against.</div>
      </div>
      {id && <PoView id={id} />}
    </div>
  );
}
