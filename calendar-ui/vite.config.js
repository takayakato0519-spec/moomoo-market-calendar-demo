import { defineConfig } from "vite";

export default defineConfig({
  define: { "process.env.NODE_ENV": JSON.stringify("production") },
  build: {
    outDir: "../calendar-assets",
    emptyOutDir: true,
    lib: { entry: "src/main.jsx", name: "MarketCalendar", formats: ["iife"], fileName: () => "calendar.js", cssFileName: "calendar" },
  },
});
