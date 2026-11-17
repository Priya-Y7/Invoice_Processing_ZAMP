import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, ClipboardList, Database, FileUp, History, LayoutDashboard, Moon, PanelLeftClose, PanelLeftOpen, ScanLine, SlidersHorizontal, Sun, UploadCloud } from "lucide-react";
import { ReactNode, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api";
import { ago } from "./lib";
import { Banner } from "./components/ui";
import { useTheme } from "./theme";
import Dashboard from "./pages/Dashboard";
import Data from "./pages/Data";
import DeepDive from "./pages/DeepDive";
import Exceptions from "./pages/Exceptions";
import HistoryPage from "./pages/History";
import RunView from "./pages/RunView";
import SettingsPage from "./pages/Settings";
import UploadPage from "./pages/Upload";

type Item = { to: string; icon: any; text: string; badge?: "tracker" };
const GROUPS: { label: string; items: Item[] }[] = [
  { label: "Workspace", items: [{ to: "/", icon: UploadCloud, text: "Upload & Run" }, { to: "/config", icon: SlidersHorizontal, text: "Configuration" }] },
  { label: "Analysis", items: [{ to: "/dashboard", icon: LayoutDashboard, text: "Dashboard" }, { to: "/exceptions", icon: ClipboardList, text: "Action Tracker", badge: "tracker" }] },
  { label: "Records", items: [{ to: "/history", icon: History, text: "Run History" }, { to: "/data", icon: Database, text: "Reference Data" }] },
];

const TITLES: [RegExp, string, string][] = [
  [/^\/run\//, "Live run", "Nine stages, one decision, every step visible"],
  [/^\/config/, "Configuration", "Set tolerances, review the policy and read the reference guide"],
  [/^\/dashboard/, "Dashboard", "Touchless rate, value at risk and invoice performance at a glance"],
  [/^\/deepdive/, "PO balance view", "How a purchase order is consumed, invoice by invoice"],
  [/^\/exceptions/, "Action Tracker", "What needs a person, why, who owns it and whether it is late"],
  [/^\/history/, "Run history", "Every invoice processed, with its verdict"],
  [/^\/data/, "Reference data", "Vendors, purchase orders and invoice history the checks read from"],
  [/^\//, "Upload & run", "Check the data is ready, then drop an invoice and watch InvoiceIQ decide"],
];

function RunGate({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  const an = useQuery({ queryKey: ["analytics", ""], queryFn: () => api("/analytics"), refetchInterval: 5000 });
  if (!an.data) return null;
  if (an.data.total > 0) return <>{children}</>;
  return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="text-center max-w-md">
        <div className="mx-auto mb-4 w-14 h-14 rounded-full bg-indigo-soft text-indigo flex items-center justify-center"><FileUp size={26} /></div>
        <div className="text-[20px] font-semibold">{title}</div>
        <div className="text-[14px] text-muted mt-2">{hint}</div>
        <Link to="/" className="btn-primary mt-6 inline-flex">Go to Upload & Run</Link>
      </div>
    </div>
  );
}

export default function App() {
  const loc = useLocation();
  const nav = useNavigate();
  const [, title, sub] = TITLES.find(([re]) => re.test(loc.pathname))!;
  const an = useQuery({ queryKey: ["analytics", ""], queryFn: () => api("/analytics"), refetchInterval: 5000 });
  const last = an.data?.last_run;
  const counts = { tracker: an.data?.open_exceptions || 0 };
  const { dark, toggle } = useTheme();
  const [collapsed, setCollapsed] = useState(() => { try { return localStorage.getItem("iq-nav") === "1"; } catch { return false; } });
  const setNav = (v: boolean) => { setCollapsed(v); try { localStorage.setItem("iq-nav", v ? "1" : "0"); } catch {} };
  return (
    <div className="flex h-full">
      <aside className={`${collapsed ? "w-[68px]" : "w-[236px]"} shrink-0 bg-navy text-white flex flex-col transition-[width] duration-200 border-r border-white/5`}>
        <div className={`py-5 flex items-center ${collapsed ? "justify-center px-0" : "px-5 gap-2.5"}`}>
          <div className="w-8 h-8 rounded-lg bg-indigo flex items-center justify-center shrink-0"><ScanLine size={18} /></div>
          {!collapsed && <div className="flex-1 min-w-0"><div className="font-bold text-[16px] leading-none">InvoiceIQ</div><div className="text-[11px] text-white/60 mt-1">Invoice to decision</div></div>}
          {!collapsed && <button onClick={() => setNav(true)} title="Collapse sidebar" className="text-white/60 hover:text-white p-1 rounded hover:bg-white/10"><PanelLeftClose size={17} /></button>}
        </div>
        {collapsed && <button onClick={() => setNav(false)} title="Expand sidebar" className="mx-auto mb-2 text-white/60 hover:text-white p-1.5 rounded hover:bg-white/10"><PanelLeftOpen size={18} /></button>}
        <nav className={`flex-1 ${collapsed ? "px-2" : "px-3"} space-y-4 mt-1 overflow-y-auto overflow-x-hidden`}>
          {GROUPS.map((g) => (
            <div key={g.label}>
              {collapsed ? <div className="mx-3 mb-2 border-t border-white/10" /> : <div className="px-2 mb-1.5 text-[10px] tracking-[0.14em] uppercase text-white/55 font-semibold">{g.label}</div>}
              {g.items.map((it) => (
                <NavLink key={it.to} to={it.to} end={it.to === "/"} title={collapsed ? it.text : undefined}
                  className={({ isActive }) => `relative flex items-center ${collapsed ? "justify-center px-0" : "gap-2.5 px-2.5"} py-2 rounded-lg text-[13.5px] mb-0.5 ${isActive ? "bg-white/10 text-white font-semibold" : "text-white/75 hover:bg-white/5"}`}>
                  <it.icon size={collapsed ? 18 : 16} />{!collapsed && <span className="flex-1">{it.text}</span>}
                  {it.badge && counts[it.badge] > 0 && (collapsed
                    ? <span className="absolute top-0.5 right-1.5 min-w-[16px] h-4 px-1 rounded-full bg-indigo text-[10px] font-bold flex items-center justify-center">{counts[it.badge]}</span>
                    : <span className="min-w-[20px] h-5 px-1.5 rounded-full bg-indigo text-[11px] font-bold flex items-center justify-center">{counts[it.badge]}</span>)}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className={`p-4 border-t border-white/10 text-[11px] ${collapsed ? "flex justify-center" : ""}`}>
          <div className="flex items-center gap-2 text-white/85 font-medium" title={`Session ready · ${an.data?.total ?? 0} runs`}><span className="w-2 h-2 rounded-full bg-ok animate-pulse shrink-0" />{!collapsed && <>Session ready · {an.data?.total ?? 0} run{an.data?.total === 1 ? "" : "s"}</>}</div>
          {!collapsed && <div className="text-white/60 mt-1.5">AI reads, rules decide.<br />Every verdict traces to a rule id.</div>}
        </div>
      </aside>
      <main className="flex-1 min-w-0 overflow-y-auto">
        <header className="sticky top-0 z-10 bg-bg/90 backdrop-blur px-8 py-3.5 flex items-center justify-between border-b border-line">
          <div><h1 className="text-[20px] font-bold leading-tight">{title}</h1><p className="text-[13px] text-muted">{sub}</p></div>
          <div className="flex items-center gap-3">
            {last && <button onClick={() => nav(`/run/${last.run_id}`)} className="hidden lg:flex items-center gap-2 text-[12px] text-muted hover:text-ink">
              <Activity size={14} />Last run {ago(last.at)} · <span className="font-semibold text-ink">{last.invoice_number || last.filename}</span></button>}
            <button onClick={toggle} title={dark ? "Switch to light mode" : "Switch to dark mode"} aria-label="Toggle dark mode" className="w-9 h-9 rounded-lg border border-line bg-surface text-ink flex items-center justify-center hover:bg-bg">{dark ? <Sun size={16} /> : <Moon size={16} />}</button>
            <button className="btn-primary" onClick={() => nav("/")}><UploadCloud size={15} />Run invoice</button>
          </div>
        </header>
        <div className="px-8 py-6 max-w-[1320px]">
          {an.isError && (
            <div className="mb-5"><Banner tone="warn" icon={<AlertTriangle size={16} />}>
              <b>Can't reach the InvoiceIQ server.</b> Start it in Terminal with <span className="font-mono">cd ~/Desktop/invoiceiq/backend &amp;&amp; PYTHONPATH=. python3 -m uvicorn app.main:app --port 8000</span>, then refresh this page.
            </Banner></div>
          )}
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/run/:id" element={<RunView />} />
            <Route path="/config" element={<SettingsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/dashboard" element={<RunGate title="Your dashboard is empty" hint="Upload an invoice on the Upload & Run page. Metrics, charts and vendor risk will appear here after the first run."><Dashboard /></RunGate>} />
            <Route path="/actions" element={<Navigate to="/exceptions" replace />} />
            <Route path="/summary" element={<Navigate to="/history" replace />} />
            <Route path="/waterfall" element={<Navigate to="/dashboard" replace />} />
            <Route path="/studio" element={<Navigate to="/dashboard" replace />} />
            <Route path="/deepdive" element={<DeepDive />} />
            <Route path="/exceptions" element={<RunGate title="Nothing to track yet" hint="Upload an invoice on the Upload & Run page. Anything that needs a person to decide will be tracked here."><Exceptions /></RunGate>} />
            <Route path="/history" element={<RunGate title="No runs yet" hint="Upload an invoice on the Upload & Run page. Every invoice you run will be listed here with its decision."><HistoryPage /></RunGate>} />
            <Route path="/data" element={<Data />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}
