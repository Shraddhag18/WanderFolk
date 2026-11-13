import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

// The start page is plain HTML in public/index.html (built with the taste-skill kit in public/assets).
// The trip app is the React build at /trip/. On Vercel (VERCEL=1) the build goes to web/dist, which the
// "web" service serves; locally it goes to ../public, which server.py serves. Vite's own files go to /static so they never mix with the kit's /assets.
// In dev, /api calls go to the FastAPI server on port 8000.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: process.env.VERCEL ? "dist" : "../public",
    emptyOutDir: true,
    assetsDir: "static",
    rollupOptions: { input: { trip: resolve(__dirname, "trip/index.html") } },
  },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
