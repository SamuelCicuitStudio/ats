import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/cv": "http://localhost:8000",
      "/jd": "http://localhost:8000",
      "/match": "http://localhost:8000",
      "/tests": "http://localhost:8000",
      "/kpi": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
