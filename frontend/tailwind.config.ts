import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#f0fdf4",  // Green: very light
          100: "#dcfce7",  // Green: light
          200: "#bbf7d0",  // Green: lighter
          300: "#86efac",  // Green: semi-light
          400: "#4ade80",  // Green: medium
          500: "#22c55e",  // Green: vibrant
          600: "#16a34a",  // Primary green
          700: "#15803d",  // Green: darker
          800: "#166534",  // Green: dark
          900: "#14532d",  // Green: very dark
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0.375rem",
        lg: "0.5rem",
        xl: "0.75rem",
        "2xl": "1rem",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "slide-in": { from: { transform: "translateX(-100%)" }, to: { transform: "translateX(0)" } },
        "nav-progress": {
          "0%":   { transform: "scaleX(0.04)", opacity: "0.9" },
          "40%":  { transform: "scaleX(0.52)", opacity: "1" },
          "75%":  { transform: "scaleX(0.78)", opacity: "1" },
          "100%": { transform: "scaleX(0.88)", opacity: "1" },
        },
        "skeleton-shimmer": {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
        "slide-in": "slide-in 0.3s ease-out",
        "nav-progress": "nav-progress 1.8s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        "skeleton-shimmer": "skeleton-shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};

export default config;

