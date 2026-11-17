export function inr(n: number | null | undefined, decimals = 2): string {
  if (n === null || n === undefined || isNaN(n as number)) return "—";
  return (n < 0 ? "-" : "") + "₹" + Math.abs(Number(n)).toLocaleString("en-IN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
export const inrShort = (n: number) => inr(n, 0);
export function ms(n?: number | null): string {
  if (n === null || n === undefined) return "—";
  return n < 1000 ? `${n} ms` : `${(n / 1000).toFixed(1)} s`;
}
export function ago(iso?: string | null): string {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
}
export const VERDICT: Record<string, { fg: string; bg: string; bar: string; label: string }> = {
  Approve: { fg: "text-ok", bg: "bg-ok-soft", bar: "#1F9D55", label: "Approve" },
  Review: { fg: "text-warn", bg: "bg-warn-soft", bar: "#D98A00", label: "Review" },
  Reject: { fg: "text-bad", bg: "bg-bad-soft", bar: "#D64545", label: "Reject" },
};
export const STAGE_NAMES = ["Ingest", "Extract", "Validate", "Vendor", "Duplicate", "PO match", "Numbers", "Decide", "Output"];
export const STAGE_FULL = ["Ingest", "Extract", "Validate completeness", "Vendor check", "Duplicate check", "PO match", "Three-way numeric check", "Decide", "Output"];
export const STAGE_BLURB = [
  "Is this a usable file, and have we seen it before?", "What does the invoice say?", "Is anything missing or malformed?",
  "Known, approved vendor with matching details?", "Have we already processed this invoice?", "Which purchase order does it belong to?",
  "Do the numbers agree with the PO and the tax maths?", "Approve, Review or Reject, and why?", "What is recorded and what happens next?",
];

// Chart palette (teal / magenta / blue / green / red / purple)
export const CH = { teal: "#1F6F82", magenta: "#C84B9A", blue: "#2F6FDE", green: "#2FB344", red: "#E0563C", purple: "#9B87F5" };
export const CHART_VERDICT: Record<string, string> = { Approve: CH.green, Review: CH.magenta, Reject: CH.red };
