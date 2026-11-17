import { useQuery } from "@tanstack/react-query";
import { Activity, AlertOctagon, CheckCircle2, Download, FileSearch, Hourglass, ShieldAlert, Wallet, XCircle, Zap } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Sector, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useChartColors } from "../theme";
import { ChartTip, Collapsible, Empty, Kpi, LevelChip, Progress, Section, VerdictBadge } from "../components/ui";
import { CH, CHART_VERDICT, VERDICT, ago, inr, inrShort, ms } from "../lib";


export default function Dashboard() {
  const cc = useChartColors();
  const AX = { fontSize: 11, fill: cc.axis };
  const GRID = cc.grid;
  const [vendor, setVendor] = useState("");
  const [hov, setHov] = useState<number | null>(null);
  const an = useQuery({ queryKey: ["analytics", vendor], queryFn: () => api(`/analytics${vendor ? `?vendor=${encodeURIComponent(vendor)}` : ""}`), refetchInterval: 4000 });
  const all = useQuery({ queryKey: ["analytics", ""], queryFn: () => api("/analytics") });
  const runs = useQuery({ queryKey: ["runs"], queryFn: () => api("/runs"), refetchInterval: 4000 });
  const mx = useQuery({ queryKey: ["matrix"], queryFn: () => api("/matrix"), refetchInterval: 4000 });
  const act = useQuery({ queryKey: ["activity"], queryFn: () => api("/activity"), refetchInterval: 4000 });
  const wf = useQuery({ queryKey: ["waterfall"], queryFn: () => api("/waterfall"), refetchInterval: 4000 });
  const gd = useQuery({ queryKey: ["guide"], queryFn: () => api("/guide") });
  const s = an.data;
  if (!s) return null;
  if (!all.data?.total) return <div className="card"><Empty title="No runs yet" hint="Process a sample on the Upload page and the dashboard fills in live." /></div>;
  const donut = ["Approve", "Review", "Reject"].map((k) => ({ name: k, value: s[k.toLowerCase()] }));
  const max = Math.max(1, ...mx.data?.cells?.map((c: any) => c.count) || [1]);
  const vrows = (runs.data || []).filter((r: any) => !vendor || r.vendor_name === vendor);
  return (
    <div className="space-y-5">
      <div className="card px-4 py-3 flex items-end gap-4">
        <label className="flex items-center gap-3"><span className="text-[10.5px] uppercase tracking-wide font-semibold text-muted">Vendor</span>
          <select className="input !py-1.5 !w-72" value={vendor} onChange={(e) => setVendor(e.target.value)}><option value="">All vendors</option>{all.data.vendors.map((v: string) => <option key={v}>{v}</option>)}</select></label>
        <div className="flex-1" />
        <div className="text-[12px] text-muted pb-2">Live · refreshes every 4 s · {s.total} run{s.total === 1 ? "" : "s"} in view</div>
        <a className="btn-ghost !py-1.5" href="/api/runs/export.csv"><Download size={13} />Export CSV</a>
      </div>

      <Collapsible title="Metric definitions" right={<span className="text-[11.5px] text-muted">how each number is calculated</span>}>
        <div className="grid grid-cols-3 gap-x-8 gap-y-5">
          <div className="col-span-1">
            <div className="text-[13px] font-bold mb-2">Vendor risk classification</div>
            {[["Low", "0–29", "Mostly approved. No action needed."], ["Medium", "30–59", "Several exceptions. Watch and follow up."], ["High", "60+", "Frequent Review or Reject. Escalate to Procurement."]].map(([k, r, t]) => (
              <div key={k} className="flex items-start gap-3 border-l-[3px] pl-3 py-1.5 mb-2" style={{ borderColor: k === "Low" ? "#1F9D55" : k === "Medium" ? "#D98A00" : "#D64545" }}><LevelChip level={k} /><div className="text-[12.5px] text-body"><b>Score {r}</b> — {t}</div></div>))}
          </div>
          <div className="col-span-2 grid grid-cols-2 gap-4">
            {(gd.data?.metrics || []).map((m: any) => (
              <div key={m.name}><div className="text-[13px] font-bold">{m.name}</div><div className="text-[12.5px] text-body mt-0.5">{m.text}</div>
                <code className="block mt-1.5 text-[11.5px] bg-indigo-soft text-indigo-dark rounded px-2 py-1 font-mono">{m.formula}</code></div>))}
          </div>
        </div>
      </Collapsible>

      <div className="grid grid-cols-4 gap-4">
        <Kpi label="Invoices processed" value={s.total} sub={inrShort(s.value_processed) + " total value"} icon={<Activity size={14} />} />
        <Kpi label="Touchless rate" value={`${s.touchless_rate}%`} color="#7048E8" sub="approved, no human" icon={<Zap size={14} />} />
        <Kpi label="Approved" value={s.approve} color={CH.green} sub={inrShort(s.value_by_decision.Approve || 0)} icon={<CheckCircle2 size={14} />} />
        <Kpi label="Needs review" value={s.review} color={CH.magenta} sub={inrShort(s.value_by_decision.Review || 0)} icon={<ShieldAlert size={14} />} />
        <Kpi label="Rejected" value={s.reject} color={CH.red} sub={inrShort(s.value_by_decision.Reject || 0)} icon={<XCircle size={14} />} />
        <Kpi label="Value at risk" value={inrShort(s.value_at_risk)} color={CH.red} sub="Review + Reject" icon={<Wallet size={14} />} />
        <Kpi label="Time saved (est.)" value={`${s.time_saved_min} min`} color={CH.green} sub={`assumes ${s.manual_min_assumption} min / invoice`} icon={<Hourglass size={14} />} />
        <Kpi label="Open exceptions" value={s.open_exceptions} color="#7048E8" sub={`${s.overdue} overdue · ${s.overrides} overrides`} icon={<AlertOctagon size={14} />} />
      </div>

      <div className="grid grid-cols-12 gap-5">
        <Section title="Decisions" className="col-span-3">
          <div className="p-3">
            <div className="h-[200px] relative"><ResponsiveContainer><PieChart>
              <Pie data={donut} dataKey="value" innerRadius={60} outerRadius={86} paddingAngle={3} cornerRadius={4} stroke="none" animationDuration={800}
                activeIndex={hov ?? undefined} activeShape={(p: any) => <Sector {...p} outerRadius={p.outerRadius + 7} />}
                onMouseEnter={(_: any, i: number) => setHov(i)} onMouseLeave={() => setHov(null)}>{donut.map((d) => <Cell key={d.name} fill={CHART_VERDICT[d.name]} />)}</Pie>
            </PieChart></ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <div className="text-[26px] font-bold leading-none" style={{ color: hov != null ? CHART_VERDICT[donut[hov].name] : undefined }}>{hov != null ? donut[hov].value : s.total}</div>
                <div className="text-[11.5px] text-muted mt-1">{hov != null ? `${donut[hov].name} · ${s.total ? Math.round((donut[hov].value / s.total) * 100) : 0}%` : "invoices"}</div>
              </div></div>
            <div className="flex justify-center gap-4 text-[12px] mt-2">{donut.map((d) => <span key={d.name} className="inline-flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full" style={{ background: CHART_VERDICT[d.name] }} />{d.name}</span>)}</div>
          </div>
        </Section>
        <Section title="Decision trend" className="col-span-5">
          <div className="h-[250px] p-2"><ResponsiveContainer><BarChart data={s.trend}><XAxis dataKey="day" tick={AX} axisLine={false} tickLine={false} /><YAxis hide allowDecimals={false} /><Tooltip content={<ChartTip />} cursor={cc.cursor} />
            {["Approve", "Review", "Reject"].map((k) => <Bar key={k} dataKey={k} stackId="a" fill={CHART_VERDICT[k]} barSize={34} activeBar={{ fillOpacity: 0.78 }} animationDuration={700} />)}</BarChart></ResponsiveContainer></div>
        </Section>
        <Section title="Value by decision" className="col-span-4">
          <div className="p-4 space-y-3.5">{["Approve", "Review", "Reject"].map((k) => {
            const v = s.value_by_decision[k] || 0; const p = s.value_processed ? (v / s.value_processed) * 100 : 0;
            return <div key={k}><div className="flex justify-between text-[12.5px]"><span className="font-medium">{k}</span><span className="tabular-nums">{inrShort(v)} <span className="text-muted">· {p.toFixed(0)}%</span></span></div>
              <div className="h-2.5 rounded-full bg-line mt-1 overflow-hidden"><div className="h-full" style={{ width: `${p}%`, background: CHART_VERDICT[k] }} /></div></div>;
          })}
            <div className="pt-2 border-t border-line text-[12px] text-muted">Large invoices by amount band</div>
            <div className="h-[88px]"><ResponsiveContainer><BarChart data={s.bands} layout="vertical" margin={{ left: 20 }}><XAxis type="number" hide /><YAxis type="category" dataKey="band" tick={AX} width={80} axisLine={false} tickLine={false} /><Tooltip content={<ChartTip />} cursor={cc.cursor} />
              {["Approve", "Review", "Reject"].map((k) => <Bar key={k} dataKey={k} stackId="a" fill={CHART_VERDICT[k]} barSize={10} />)}</BarChart></ResponsiveContainer></div>
          </div>
        </Section>
      </div>

      <div className="grid grid-cols-12 gap-5">
        <Section title="Stage funnel · where invoices get stuck" className="col-span-7" right={<span className="text-[12px] text-muted">clean · flagged · failed per stage</span>}>
          <div className="h-[290px] p-2"><ResponsiveContainer><BarChart data={wf.data?.funnel || []}>
            <XAxis dataKey="name" tick={{ ...AX, fontSize: 10 }} interval={0} axisLine={false} tickLine={false} /><YAxis hide allowDecimals={false} /><Tooltip content={<ChartTip />} cursor={cc.cursor} />
            <Bar dataKey="clean" name="Clean" stackId="a" fill={CH.teal} barSize={30} activeBar={{ fillOpacity: 0.78 }} /><Bar dataKey="flagged" name="Flagged" stackId="a" fill={CH.magenta} activeBar={{ fillOpacity: 0.78 }} /><Bar dataKey="failed" name="Failed" stackId="a" fill={CH.red} radius={[4, 4, 0, 0]} activeBar={{ fillOpacity: 0.78 }} />
          </BarChart></ResponsiveContainer></div>
        </Section>
        <Section title="Average time per stage" className="col-span-5">
          <div className="h-[280px] p-2"><ResponsiveContainer><BarChart data={s.stage_stats} margin={{ left: 18, right: 8 }}><XAxis dataKey="name" tick={{ ...AX, fontSize: 10 }} interval={0} angle={-30} textAnchor="end" height={54} axisLine={false} tickLine={false} /><YAxis hide />
            <Tooltip content={<ChartTip fmt={(v: any) => `${v} ms`} />} cursor={cc.cursor} /><Bar dataKey="avg_ms" name="Avg time" fill={CH.teal} radius={[5, 5, 0, 0]} barSize={22} activeBar={{ fillOpacity: 0.78 }} /></BarChart></ResponsiveContainer></div>
        </Section>
      </div>
      <div className="grid grid-cols-12 gap-5">
        <Section title="Why invoices are stopped · rule hits" className="col-span-8">
          {s.rule_hits.length ? <div className="h-[280px] p-2"><ResponsiveContainer><BarChart data={s.rule_hits} layout="vertical" margin={{ left: 40, right: 20 }}>
            <XAxis type="number" hide allowDecimals={false} /><YAxis type="category" dataKey="rule" tick={AX} width={40} axisLine={false} tickLine={false} />
            <Tooltip content={<ChartTip />} cursor={cc.cursor} />
            <Bar dataKey="fail" name="Failures" stackId="a" fill={CH.red} barSize={14} activeBar={{ fillOpacity: 0.78 }} /><Bar dataKey="warn" name="Warnings" stackId="a" fill={CH.magenta} radius={[0, 4, 4, 0]} barSize={14} activeBar={{ fillOpacity: 0.78 }} /></BarChart></ResponsiveContainer></div> : <Empty title="Nothing stopped yet" />}
        </Section>
        <Section title="Extraction confidence" className="col-span-4">
          <div className="p-3 h-[150px]"><ResponsiveContainer><BarChart data={s.confidence_hist}><XAxis dataKey="bucket" tick={{ ...AX, fontSize: 9.5 }} interval={0} axisLine={false} tickLine={false} /><YAxis hide allowDecimals={false} /><Tooltip content={<ChartTip />} cursor={cc.cursor} />
            <Bar dataKey="count" name="Invoices" radius={[4, 4, 0, 0]} activeBar={{ fillOpacity: 0.78 }}>{s.confidence_hist.map((_: any, i: number) => <Cell key={i} fill={i < 2 ? CH.red : i === 2 ? CH.magenta : CH.green} />)}</Bar></BarChart></ResponsiveContainer></div>
          <div className="px-4 pb-4 space-y-2">{s.field_confidence.map((f: any) => <Progress key={f.field} label={f.field.replace(/_/g, " ")} value={Math.round(f.avg * 100)} />)}</div>
        </Section>
      </div>
      <Section title="Vendor risk" right={<span className="text-[12px] text-muted">score = (Review + 2 × Reject) ÷ (2 × runs)</span>}>
        <table className="w-full text-[13px]"><thead><tr><th className="th">Vendor</th><th className="th text-right">Runs</th><th className="th text-right">Approve</th><th className="th text-right">Review</th><th className="th text-right">Reject</th><th className="th text-right">Value</th><th className="th text-right">At risk</th><th className="th w-40">Risk</th><th className="th">Top rule</th></tr></thead>
          <tbody>{s.vendor_risk.map((v: any) => (
            <tr key={v.vendor} className="hover:bg-bg"><td className="td font-medium">{v.vendor}</td><td className="td text-right tabular-nums">{v.runs}</td><td className="td text-right text-ok tabular-nums">{v.approve}</td><td className="td text-right text-warn tabular-nums">{v.review}</td><td className="td text-right text-bad tabular-nums">{v.reject}</td>
              <td className="td text-right tabular-nums">{inrShort(v.value)}</td><td className="td text-right tabular-nums font-semibold">{inrShort(v.at_risk)}</td>
              <td className="td"><div className="flex items-center gap-2"><LevelChip level={v.risk} /><div className="flex-1"><Progress value={v.risk_score} color={v.risk === "High" ? "#D64545" : v.risk === "Medium" ? "#D98A00" : "#1F9D55"} /></div></div></td>
              <td className="td font-mono text-[12px] text-muted">{v.top_rule || "—"}</td></tr>))}</tbody></table>
      </Section>

      <Section title="Exception matrix · vendor × cause" right={<span className="text-[12px] text-muted">darker = more invoices</span>}>
        {mx.data?.cells?.length ? <div className="overflow-x-auto"><table className="w-full text-[12.5px]">
          <thead><tr><th className="th">Vendor</th>{mx.data.rules.map((r: any) => <th key={r.rule} className="th text-center" title={r.name}>{r.rule}<div className="normal-case font-normal text-[10px] tracking-normal">{r.name}</div></th>)}</tr></thead>
          <tbody>{mx.data.vendors.map((v: string) => <tr key={v}><td className="td font-medium">{v}</td>{mx.data.rules.map((r: any) => {
            const c = mx.data.cells.find((x: any) => x.vendor === v && x.rule === r.rule)?.count || 0;
            return <td key={r.rule} className="td text-center p-1"><div className="rounded-md py-1.5 font-semibold" style={{ background: c ? `rgba(200,75,154,${0.15 + 0.7 * (c / max)})` : "transparent", color: c ? (c / max > 0.6 ? "#fff" : cc.redText) : "#CBD2DE" }}>{c || "·"}</div></td>;
          })}</tr>)}</tbody></table></div> : <Empty title="No exceptions yet" />}
      </Section>

      <div className="grid grid-cols-12 gap-5">
        <Section title="Largest flagged invoices" className="col-span-7" right={<Link to="/exceptions" className="text-[12.5px] text-indigo font-semibold">Open action tracker</Link>}>
          <table className="w-full text-[13px]"><thead><tr><th className="th">Invoice</th><th className="th">Vendor</th><th className="th text-right">Total</th><th className="th">Decision</th><th className="th">Rule</th><th className="th">Status</th></tr></thead>
            <tbody>{s.top_flagged.slice(0, 6).map((x: any) => (
              <tr key={x.run_id} className="hover:bg-bg"><td className="td"><Link className="text-indigo font-medium" to={`/run/${x.run_id}`}>{x.invoice_number || "—"}</Link></td><td className="td">{x.vendor}</td>
                <td className="td text-right tabular-nums">{inr(x.total, 0)}</td><td className="td"><VerdictBadge v={x.decision} /></td><td className="td font-mono text-[12px] text-muted">{x.top_rule}</td><td className="td text-muted">{x.exception_status || "—"}</td></tr>))}</tbody></table>
        </Section>
        <Section title="Activity" className="col-span-5">
          <div className="max-h-[300px] overflow-y-auto divide-y divide-line">{(act.data || []).slice(0, 10).map((e: any, i: number) => (
            <Link key={i} to={`/run/${e.run_id}`} className="flex items-start gap-3 px-4 py-2.5 hover:bg-bg">
              <span className={`mt-1.5 w-2 h-2 rounded-full shrink-0 ${e.kind === "run" ? (e.decision === "Approve" ? "bg-ok" : e.decision === "Reject" ? "bg-bad" : "bg-warn") : e.kind === "override" ? "bg-ai" : "bg-ok"}`} />
              <span className="flex-1 text-[12.5px] leading-snug">{e.text}</span><span className="text-[11px] text-muted whitespace-nowrap">{ago(e.ts)}</span></Link>))}</div>
        </Section>
      </div>

      <Section title="Recent runs" right={<FileSearch size={14} className="text-muted" />}>
        <table className="w-full text-[13px]"><thead><tr><th className="th">File</th><th className="th">Vendor</th><th className="th">Invoice</th><th className="th text-right">Total</th><th className="th">Decision</th><th className="th">Top rule</th><th className="th">When</th></tr></thead>
          <tbody>{vrows.slice(0, 8).map((r: any) => (
            <tr key={r.run_id} className="hover:bg-bg"><td className="td"><Link className="text-indigo font-medium" to={`/run/${r.run_id}`}>{r.filename}</Link></td><td className="td">{r.vendor_name}</td><td className="td">{r.invoice_number || "—"}</td>
              <td className="td text-right tabular-nums">{inr(r.total)}</td><td className="td"><VerdictBadge v={r.final_decision || r.decision} /></td><td className="td font-mono text-[12px] text-muted">{r.top_rule || "—"}</td><td className="td text-muted">{ago(r.started_at)}</td></tr>))}</tbody></table>
      </Section>
    </div>
  );
}
