import { useEffect, useRef, useState } from "react";

export async function api<T = any>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch("/api" + path, opts);
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = j.detail || msg; } catch {}
    throw new Error(msg);
  }
  return r.json();
}
export const post = (p: string, body?: any) => api(p, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
export const put = (p: string, body: any) => api(p, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
export const patch = (p: string, body: any) => api(p, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export async function uploadFile(file: File): Promise<string> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch("/api/runs", { method: "POST", body: fd });
  if (!r.ok) { let m = "Upload failed"; try { m = (await r.json()).detail; } catch {} throw new Error(m); }
  return (await r.json()).run_id;
}

export type StageState = { status: "pending" | "running" | "pass" | "warn" | "fail" | "error" | "skipped"; result?: any };

/** Subscribes to the SSE stream of one run and keeps a per-stage state map. */
export function useRunStream(runId: string | undefined) {
  const [stages, setStages] = useState<Record<number, StageState>>({});
  const [done, setDone] = useState<any>(null);
  const [started, setStarted] = useState(false);
  const es = useRef<EventSource | null>(null);
  useEffect(() => {
    setStages({}); setDone(null); setStarted(false);
    if (!runId) return;
    const src = new EventSource(`/api/runs/${runId}/events`);
    es.current = src;
    src.onmessage = (m) => {
      const ev = JSON.parse(m.data);
      if (ev.type === "run_started" || ev.type === "queued") setStarted(true);
      if (ev.type === "stage_started") setStages((s) => ({ ...s, [ev.stage_no]: { status: "running" } }));
      if (ev.type === "stage_result") setStages((s) => ({ ...s, [ev.stage_no]: { status: ev.status, result: ev } }));
      if (ev.type === "run_completed") { setDone(ev); src.close(); }
    };
    src.onerror = () => { src.close(); };
    return () => src.close();
  }, [runId]);
  return { stages, done, started };
}
