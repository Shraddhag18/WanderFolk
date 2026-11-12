import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Builds into ../public, which Vercel serves from its CDN (and server.py serves locally).
// In dev, /api calls go to the FastAPI server on port 8000.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../public", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
