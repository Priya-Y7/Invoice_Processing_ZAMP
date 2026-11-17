import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, AlertOctagon, CheckCheck, Siren, Wallet } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api, patch } from "../api";
import { BigCard, Empty, LevelChip, Section, Tabs, VerdictBadge } from "../components/ui";
import { ago, inr, inrShort } from "../lib";

const age = (h: number) => (h < 1 ? "<1 h" : h < 48 ? `${Math.round(h)} h` : `${Math.round(h / 24)} d`);
const ASSIGNEES = ["AP Manager", "AP Clerk", "Procurement", "Finance Controller"];

export default function Exceptions() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["actions"], queryFn: () => api("/actions"), refetchInterval: 4000 });
  const act = useQuery({ queryKey: ["activity"], queryFn: () => api("/activity"), refetchInterval: 4000 });
  const upd = useMutation({ mutationFn: (v: { id: number; body: any }) => patch(`/exceptions/${v.id}`, v.body), onSuccess: () => { ["actions", "exceptions", "stats", "analytics", "activity"].forEach((k) => qc.invalidateQueries({ queryKey: [k] })); } });
  const [stage, setStage] = useState("");
  const [status, setStatus] = useState("open");
  const d = q.data;
  if (!d) return null;
  const rows = d.rows.filter((r: any) => (!stage || String(r.stage_no) === stage) && (status === "all" || (status === "open" ? r.status !== "Resolved" : r.status === "Resolved")));
  const b = d.buckets.find((x: any) => String(x.stage_no) === stage);
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-4 gap-4">
        <BigCard icon={<Siren size={18} />} color="#D64545" value={d.critical} unit="invoices" title="Critical" sub="Rejected: return to vendor or escalate" tag="Reject" />
        <BigCard icon={<AlertOctagon size={18} />} color="#D98A00" value={d.moderate} unit="invoices" title="Needs a decision" sub="Review within the stage turnaround" tag="Review" />
        <BigCard icon={<CheckCheck size={18} />} color="#1F9D55" value={d.resolved} unit="invoices" title="Resolved" sub="Closed or overridden" tag="done" />
        <BigCard icon={<Wallet size={18} />} color="#7048E8" value={inrShort(d.value_at_risk)} title="Value at risk" sub={`${d.overdue} past standard turnaround`} tag="open items" />
      </div>

      <Section title="Where the open items are stuck" right={stage ? <button className="text-[12.5px] text-indigo font-semibold" onClick={() => setStage("")}>Show all stages</button> : <span className="text-[12px] text-muted">click a stage to filter</span>}>
        <div className="p-4 grid grid-cols-9 gap-2">{d.buckets.map((x: any) => (
          <button key={x.stage_no} onClick={() => setStage(String(x.stage_no) === stage ? "" : String(x.stage_no))} className={`rounded-lg border px-2 py-2.5 text-center ${String(x.stage_no) === stage ? "border-indigo bg-indigo-soft" : "border-line hover:bg-bg"}`}>
            <div className="text-[10px] uppercase tracking-wide text-muted font-semibold">S{x.stage_no} · {x.stage}</div>
            <div className={`text-[22px] font-bold leading-tight ${x.count ? "text-ink" : "text-line"}`}>{x.count}</div><div className="text-[10.5px] text-muted">{x.count ? inrShort(x.value) : "—"}</div></button>))}</div>
        {b && <div className="px-4 py-2.5 border-t border-line bg-bg/60 text-[13px] flex gap-6"><span><span className="text-muted">Stage</span> <b>{b.stage_no} · {b.stage}</b></span><span><span className="text-muted">Stakeholder</span> <b>{b.owner}</b></span><span><span className="text-muted">Standard turnaround</span> <b>{b.std_tat_h} h</b></span></div>}
      </Section>

      <Section title="Action queue" right={<Tabs tabs={[["open", "Open"], ["done", "Resolved"], ["all", "All"]]} value={status} onChange={setStatus} />}>
        {!rows.length ? <Empty icon={<AlertCircle size={18} />} title="Nothing here" hint="Review and Reject decisions land in this queue automatically." /> :
          <table className="w-full text-[13px]"><thead><tr><th className="th w-10">#</th><th className="th">Invoice</th><th className="th">Vendor</th><th className="th">Stage</th><th className="th">Why</th><th className="th text-right">Amount</th><th className="th">Age / SLA</th><th className="th">Assignee</th><th className="th">Status</th></tr></thead>
            <tbody>{rows.map((r: any) => (
              <tr key={r.run_id} className={`hover:bg-bg ${r.status === "Resolved" ? "opacity-60" : ""}`}>
                <td className="td text-muted">{r.rank}</td>
                <td className="td whitespace-nowrap"><Link className="text-indigo font-medium" to={`/run/${r.run_id}`}>{r.invoice_number || "—"}</Link><div className="mt-0.5"><VerdictBadge v={r.decision} /></div></td>
                <td className="td">{r.vendor}</td><td className="td whitespace-nowrap">S{r.stage_no} · {r.stage}</td>
                <td className="td max-w-[300px]"><span className="font-mono text-[11.5px] text-muted mr-1">{r.rule}</span><span className="font-medium">{r.issue}</span><div className="text-[12px] text-body line-clamp-2 mt-0.5">{r.reason}</div></td>
                <td className="td text-right tabular-nums font-medium whitespace-nowrap">{inr(r.total, 0)}</td>
                <td className="td whitespace-nowrap">{age(r.age_h)} <span className="text-muted text-[11.5px]">of {r.std_tat_h} h</span><div className="mt-0.5">{r.status === "Resolved" ? null : <LevelChip level={r.overdue ? "Overdue" : "On time"} />}</div></td>
                <td className="td"><select className="input !py-1 !w-36" value={r.owner} disabled={!r.exception_id} onChange={(ev) => upd.mutate({ id: r.exception_id, body: { assignee: ev.target.value } })}>{[...new Set([r.owner, ...ASSIGNEES])].map((a) => <option key={a}>{a}</option>)}</select></td>
                <td className="td"><select className={`input !py-1 !w-32 font-medium ${r.status === "Resolved" ? "!text-ok" : r.status === "In progress" ? "!text-warn" : "!text-bad"}`} value={r.status} disabled={!r.exception_id} onChange={(ev) => upd.mutate({ id: r.exception_id, body: { status: ev.target.value } })}>{["Open", "In progress", "Resolved"].map((a) => <option key={a}>{a}</option>)}</select></td>
              </tr>))}</tbody></table>}
      </Section>

      <Section title="Activity log" right={<span className="text-[12px] text-muted">runs, overrides and resolutions, newest first</span>}>
        <div className="divide-y divide-line max-h-[300px] overflow-y-auto">{(act.data || []).map((x: any, i: number) => (
          <Link key={i} to={`/run/${x.run_id}`} className="flex items-center gap-3 px-4 py-2.5 hover:bg-bg text-[13px]">
            <span className={`w-2 h-2 rounded-full shrink-0 ${x.kind === "run" ? (x.decision === "Approve" ? "bg-ok" : x.decision === "Reject" ? "bg-bad" : "bg-warn") : x.kind === "override" ? "bg-ai" : "bg-ok"}`} />
            <span className="flex-1">{x.text}</span>{x.rule && <span className="font-mono text-[11.5px] text-muted">{x.rule}</span>}<span className="text-[11.5px] text-muted w-20 text-right">{ago(x.ts)}</span></Link>))}</div>
      </Section>
    </div>
  );
}
