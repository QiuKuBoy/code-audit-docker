
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Dark theme (default)
        bg: {
          DEFAULT: "var(--color-bg)",
          card: "var(--color-bg-card)",
          hover: "var(--color-bg-hover)",
        },
        border: "var(--color-border)",
        accent: {
          DEFAULT: "var(--color-accent)",
          hover: "var(--color-accent-hover)",
        },
        text: {
          DEFAULT: "var(--color-text)",
          muted: "var(--color-text-muted)",
          dim: "var(--color-text-dim)",
        },
        severity: {
          critical: "#ef4444",
          high: "#f97316",
          medium: "#eab308",
          low: "#3b82f6",
        },
      },
    },
  },
  plugins: [],
}
