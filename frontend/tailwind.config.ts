import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#080B11",
        surface: "#0F172A",
        surfaceLight: "#1E293B",
        card: "rgba(15, 23, 42, 0.75)",
        border: "rgba(255, 255, 255, 0.08)",
        primary: {
          DEFAULT: "#6366F1",
          hover: "#4F46E5",
          glow: "rgba(99, 102, 241, 0.25)"
        },
        accent: {
          cyan: "#06B6D4",
          violet: "#8B5CF6",
          emerald: "#10B981",
          rose: "#F43F5E",
          amber: "#F59E0B"
        }
      },
      boxShadow: {
        glow: "0 0 25px -5px rgba(99, 102, 241, 0.3)",
        glass: "0 8px 32px 0 rgba(0, 0, 0, 0.37)"
      },
      backdropBlur: {
        xs: "2px",
      }
    },
  },
  plugins: [],
};
export default config;
