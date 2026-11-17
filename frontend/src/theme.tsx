import { createContext, ReactNode, useContext, useEffect, useState } from "react";

type Ctx = { dark: boolean; toggle: () => void };
const ThemeCtx = createContext<Ctx>({ dark: false, toggle: () => {} });

const initial = () => {
  try {
    const s = localStorage.getItem("iq-theme");
    if (s) return s === "dark";
  } catch {}
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
};

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [dark, setDark] = useState(initial);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try { localStorage.setItem("iq-theme", dark ? "dark" : "light"); } catch {}
  }, [dark]);
  return <ThemeCtx.Provider value={{ dark, toggle: () => setDark((d) => !d) }}>{children}</ThemeCtx.Provider>;
}

export const useTheme = () => useContext(ThemeCtx);

/** Colours for recharts, which cannot read Tailwind classes. */
export function useChartColors() {
  const { dark } = useTheme();
  return {
    dark, grid: dark ? "#2A3347" : "#E3E8EF", axis: dark ? "#A6B1C5" : "#1F2937",
    tip: { backgroundColor: dark ? "#151B27" : "#fff", border: `1px solid ${dark ? "#283142" : "#E3E8EF"}`, borderRadius: 8, color: dark ? "#E8ECF4" : "#0A0F19", fontSize: 12 },
    cursor: { fill: dark ? "rgba(255,255,255,.05)" : "rgba(0,0,0,.04)" },
    redText: dark ? "#FCA5A5" : "#8A2B2B",
  };
}
