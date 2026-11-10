/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        panel: "0 18px 60px rgba(15, 23, 42, 0.10)",
        glass: "0 1px 1px rgba(15,23,42,0.03), 0 20px 40px -16px rgba(30,41,59,0.16), inset 0 1px 0 rgba(255,255,255,0.6)",
        "glass-lg": "0 2px 2px rgba(15,23,42,0.04), 0 30px 60px -20px rgba(30,41,59,0.22), inset 0 1px 0 rgba(255,255,255,0.7)",
        glowTeal: "0 0 0 1px rgba(20,184,166,0.25), 0 8px 24px -8px rgba(13,148,136,0.45)",
        glowRose: "0 0 0 1px rgba(244,63,94,0.25), 0 8px 24px -8px rgba(225,29,72,0.45)",
        glowAmber: "0 0 0 1px rgba(245,158,11,0.25), 0 8px 24px -8px rgba(217,119,6,0.45)",
      },
      backgroundImage: {
        "brand-gradient": "linear-gradient(135deg, #0d9488 0%, #0891b2 45%, #6366f1 100%)",
        "brand-gradient-soft": "linear-gradient(135deg, rgba(13,148,136,0.12), rgba(99,102,241,0.12))",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(20,184,166,0.55)" },
          "50%": { boxShadow: "0 0 0 6px rgba(20,184,166,0)" },
        },
      },
      animation: {
        "pulse-glow": "pulse-glow 2s cubic-bezier(0.4,0,0.6,1) infinite",
      },
    },
  },
  plugins: [],
};
