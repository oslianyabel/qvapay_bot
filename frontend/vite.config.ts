import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// El backend FastAPI corre en :8000 por defecto. Se puede apuntar a otro host/puerto
// con VITE_API_TARGET. El proxy cubre /api (incluye el stream SSE /api/events).
const apiTarget = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
});
