import { AlertTriangle, Check, ChevronDown, ChevronUp, CircleSlash, Info, Loader2, X, Minus } from "lucide-react";
import { ReactNode, useState } from "react";
import { VERDICT } from "../lib";

export function VerdictBadge({ v, big }: { v?: string | null; big?: boolean }) {
  if (!v) return <span className="chip bg-bg text-muted">—</span>;
  const c = VERDICT[v];
  const Icon = v === "Approve" ? Check : v === "Review" ? AlertTriangle : X;
  return (
    <span className={`inline-flex items-center gap-1.5 font-semibold rounded-full ${c.bg} ${c.fg} ${big ? "px-5 py-2 text-[28px] leading-none" : "px-2.5 py-0.5 text-[12px]"}`}>
      <Icon size={big ? 26 : 13} strokeWidth={3} />{v}
    </span>
  );
}

export function StatusDot({ s, size = 22 }: { s: string; size?: number }) {
  const map: Record<string, [string, ReactNode]> = {
    pass: ["bg-ok text-white", <Check size={size * 0.6} strokeWidth={3} />],
    warn: ["bg-warn text-white", <AlertTriangle size={size * 0.55} strokeWidth={3} />],
    fail: ["bg-bad text-white", <X size={size * 0.6} strokeWidth={3} />],
    error: ["bg-ai text-white", <X size={size * 0.6} strokeWidth={3} />],
    skipped: ["bg-muted/70 text-white", <Minus size={size * 0.6} strokeWidth={3} />],
    pending: ["bg-surface border-2 border-line text-muted", null],
    running: ["bg-indigo-soft text-indigo", <Loader2 size={size * 0.75} className="animate-spin" />],
  };
  const [cls, icon] = map[s] || map.pending;
  return <span style={{ width: size, height: size }} className={`rounded-full inline-flex items-center justify-center shrink-0 ${cls}`}>{icon}</span>;
}

export const RESULT_TEXT: Record<string, string> = { pass: "text-ok", warn: "text-warn", fail: "text-bad", error: "text-ai", skipped: "text-muted" };
export const RESULT_LABEL: Record<string, string> = { pass: "Pass", warn: "Warn", fail: "Fail", error: "Error", skipped: "Skipped" };

export function Kpi({ label, value, sub, color = "#3B5BDB", icon }: { label: string; value: ReactNode; sub?: ReactNode; color?: string; icon?: ReactNode }) {
  return (
    <div className="card overflow-hidden group cursor-default transition-all duration-200 ease-out hover:-translate-y-1.5 hover:scale-[1.03] hover:shadow-[0_14px_30px_-8px_rgba(15,23,42,0.28)]" style={{ borderTop: `3px solid ${color}` }}>
      <div className="p-4">
        <div className="flex items-center justify-between text-[11px] uppercase tracking-wide font-semibold text-muted">{label}<span className="transition-transform duration-200 group-hover:scale-125 group-hover:-rotate-6" style={{ color }}>{icon}</span></div>
        <div className="text-[28px] font-bold leading-tight mt-1 transition-transform duration-200 origin-left group-hover:scale-105" style={{ color }}>{value}</div>
        {sub && <div className="text-[12px] text-muted mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

export function ConfBar({ v }: { v: number }) {
  const col = v >= 0.9 ? "#1F9D55" : v >= 0.8 ? "#D98A00" : "#D64545";
  return (
    <div className="flex items-center gap-2 w-28">
      <div className="h-1.5 flex-1 rounded-full bg-line overflow-hidden"><div className="h-full rounded-full" style={{ width: `${Math.round(v * 100)}%`, background: col }} /></div>
      <span className="text-[11px] tabular-nums text-muted w-8">{v ? v.toFixed(2) : "—"}</span>
    </div>
  );
}

export function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 bg-navy/50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="card w-full max-w-lg pop" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-line">
          <h3 className="font-semibold">{title}</h3>
          <button onClick={onClose} className="text-muted hover:text-ink"><X size={18} /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Empty({ icon, title, hint }: { icon?: ReactNode; title: string; hint?: string }) {
  return (
    <div className="text-center py-14 text-muted">
      <div className="mx-auto mb-3 w-10 h-10 rounded-full bg-bg flex items-center justify-center">{icon || <CircleSlash size={18} />}</div>
      <div className="font-semibold text-ink">{title}</div>
      {hint && <div className="text-[13px] mt-1">{hint}</div>}
    </div>
  );
}

export function Section({ title, right, children, className = "" }: { title: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={`card ${className}`}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-line">
        <h3 className="font-semibold text-[14px]">{title}</h3>{right}
      </div>
      {children}
    </div>
  );
}

export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <div className="flex items-center gap-2 mb-5">
      {steps.map((s, i) => (
        <div key={s} className="flex items-center gap-2">
          <div className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-[13px] font-medium ${i === current ? "bg-indigo text-white" : i < current ? "bg-ok-soft text-ok" : "bg-surface border border-line text-muted"}`}>
            <span className={`w-5 h-5 rounded-full inline-flex items-center justify-center text-[11px] font-bold ${i === current ? "bg-white/25" : i < current ? "bg-ok text-white" : "bg-bg"}`}>
              {i < current ? <Check size={12} strokeWidth={3} /> : i + 1}
            </span>{s}
          </div>
          {i < steps.length - 1 && <div className="w-8 h-px bg-line" />}
        </div>
      ))}
    </div>
  );
}

/** Blue/green info strip with a dismiss button, as at the top of the OrderIQ pages. */
export function Banner({ children, tone = "info", icon, onClose }: { children: ReactNode; tone?: "info" | "ok" | "warn"; icon?: ReactNode; onClose?: () => void }) {
  const t = { info: "bg-indigo-soft border-indigo/25 text-[#2F49B3] dark:text-[#A9BBFF]", ok: "bg-ok-soft border-ok/25 text-[#17784a] dark:text-[#6EE7A0]", warn: "bg-warn-soft border-warn/30 text-[#8a5a00] dark:text-[#FBC76A]" }[tone];
  return (
    <div className={`flex items-center gap-3 rounded-lg border px-4 py-2.5 text-[13px] ${t}`}>
      <span className="shrink-0">{icon || <Info size={16} />}</span><div className="flex-1">{children}</div>
      {onClose && <button onClick={onClose} className="opacity-60 hover:opacity-100"><X size={15} /></button>}
    </div>
  );
}

export function Progress({ label, value, color }: { label?: string; value: number; color?: string }) {
  const c = color || (value >= 90 ? "#1F9D55" : value >= 70 ? "#D98A00" : "#D64545");
  return (
    <div>
      {label && <div className="flex justify-between text-[12px] mb-1"><span className="text-body font-medium">{label}</span><span className="font-semibold tabular-nums">{value}%</span></div>}
      <div className="h-2 rounded-full bg-line overflow-hidden"><div className="h-full rounded-full transition-all" style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: c }} /></div>
    </div>
  );
}

export function Ring({ value, size = 120, label }: { value: number; size?: number; label?: string }) {
  const r = size / 2 - 10, c = 2 * Math.PI * r, col = value >= 90 ? "#1F9D55" : value >= 70 ? "#D98A00" : "#D64545";
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} stroke="#E3E8EF" strokeWidth="10" fill="none" />
        <circle cx={size / 2} cy={size / 2} r={r} stroke={col} strokeWidth="10" fill="none" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - value / 100)} style={{ transition: "stroke-dashoffset .6s" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center"><div className="font-bold leading-none" style={{ color: col, fontSize: size * 0.2 }}>{value}%</div>{label && <div className="text-[10.5px] uppercase tracking-wide text-muted mt-1">{label}</div>}</div>
    </div>
  );
}

export function Collapsible({ title, defaultOpen = false, children, right }: { title: string; defaultOpen?: boolean; children: ReactNode; right?: ReactNode }) {
  const [o, setO] = useState(defaultOpen);
  return (
    <div className="card">
      <button onClick={() => setO(!o)} className="w-full flex items-center justify-between px-4 py-3 text-left">
        <span className="text-[11.5px] tracking-[0.12em] uppercase font-bold text-body">{title}</span>
        <span className="flex items-center gap-3">{right}{o ? <ChevronUp size={16} className="text-muted" /> : <ChevronDown size={16} className="text-muted" />}</span>
      </button>
      {o && <div className="px-4 pb-4 border-t border-line pt-4">{children}</div>}
    </div>
  );
}

export function Tabs({ tabs, value, onChange }: { tabs: [string, string][]; value: string; onChange: (v: string) => void }) {
  return <div className="flex gap-2 flex-wrap">{tabs.map(([k, l]) => <button key={k} onClick={() => onChange(k)} className={`chip border ${value === k ? "bg-indigo text-white border-indigo" : "bg-surface border-line hover:bg-bg"}`}>{l}</button>)}</div>;
}

export function Pager({ page, pages, onChange, total, size }: { page: number; pages: number; onChange: (p: number) => void; total: number; size: number }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5 text-[12.5px] text-muted border-t border-line">
      <span>Page {page} of {pages} · {total} invoice{total === 1 ? "" : "s"} · {size} per page</span>
      <span className="flex gap-2"><button className="btn-ghost !py-1 !px-2.5" disabled={page <= 1} onClick={() => onChange(page - 1)}>Prev</button><button className="btn-ghost !py-1 !px-2.5" disabled={page >= pages} onClick={() => onChange(page + 1)}>Next</button></span>
    </div>
  );
}

/** Small icon tile card with a coloured top border, used for the Action Planning style KPIs. */
export function BigCard({ icon, tag, value, unit, title, sub, color }: { icon: ReactNode; tag?: string; value: ReactNode; unit?: string; title: string; sub?: string; color: string }) {
  return (
    <div className="card overflow-hidden" style={{ borderTop: `3px solid ${color}` }}>
      <div className="p-4">
        <div className="flex items-start justify-between"><span className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ background: color + "1A", color }}>{icon}</span>{tag && <span className="text-[10.5px] text-muted bg-bg rounded px-2 py-0.5">{tag}</span>}</div>
        <div className="mt-3 flex items-baseline gap-1.5"><span className="text-[30px] font-bold leading-none" style={{ color }}>{value}</span>{unit && <span className="text-[13px] text-muted">{unit}</span>}</div>
        <div className="text-[13.5px] font-semibold mt-1.5">{title}</div>{sub && <div className="text-[12px] text-muted">{sub}</div>}
      </div>
    </div>
  );
}

export function LevelChip({ level }: { level?: string | null }) {
  if (!level) return null;
  const c: Record<string, string> = { Critical: "bg-bad-soft text-bad", High: "bg-bad-soft text-bad", Medium: "bg-warn-soft text-warn", Low: "bg-ok-soft text-ok", Overdue: "bg-bad-soft text-bad", "On time": "bg-ok-soft text-ok" };
  return <span className={`chip !py-0 text-[11px] ${c[level] || "bg-bg text-muted"}`}>{level}</span>;
}

export const CODE_COLORS = ["#1F6F82", "#9B87F5", "#2FB344", "#C84B9A", "#E0563C", "#2F6FDE"];

export function ChartTip({ active, payload, label, fmt }: any) {
  if (!active || !payload?.length) return null;
  const rows = payload.filter((p: any) => p.name !== "base" && p.value != null && (p.value !== 0 || payload.length === 1));
  if (!rows.length) return null;
  return (
    <div className="rounded-lg border border-line bg-surface shadow-lg px-3 py-2 text-[12px] min-w-[120px]">
      {label != null && label !== "" && <div className="font-semibold mb-1 text-ink">{label}</div>}
      {rows.map((p: any, i: number) => (
        <div key={i} className="flex items-center gap-2"><span className="w-2 h-2 rounded-full shrink-0" style={{ background: p.color || p.payload?.fill || p.fill }} /><span className="text-muted">{p.name}</span><b className="ml-auto pl-4 tabular-nums text-ink">{fmt ? fmt(p.value, p) : p.value}</b></div>
      ))}
    </div>
  );
}
