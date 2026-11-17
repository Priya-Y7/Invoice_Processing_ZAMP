/** @type {import('tailwindcss').Config} */
const v = (n) => `rgb(var(--${n}) / <alpha-value>)`;
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"] },
      colors: {
        navy: v("navy"), ink: v("ink"), bg: v("bg"), surface: v("surface"), line: v("line"), line2: v("line2"), muted: v("muted"), body: v("body"), head: v("head"),
        indigo: { DEFAULT: v("indigo"), dark: v("indigo-dark"), soft: v("indigo-soft") },
        ok: { DEFAULT: v("ok"), soft: v("ok-soft") }, warn: { DEFAULT: v("warn"), soft: v("warn-soft") },
        bad: { DEFAULT: v("bad"), soft: v("bad-soft") }, ai: { DEFAULT: v("ai"), soft: v("ai-soft") },
      },
      boxShadow: { card: "0 1px 2px rgba(16,24,40,.05), 0 1px 3px rgba(16,24,40,.06)" },
    },
  },
  plugins: [],
};
