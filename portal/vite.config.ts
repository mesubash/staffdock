import path from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: open http://staffdock.localhost:8080/staff (API proxied to the bench on :8000).
// Build: emits portal.js/portal.css into the Frappe app; www/staff.html loads them.
const frappe = "http://staffdock.localhost:8000";

export default defineConfig(({ command }) => ({
  base: command === "build" ? "/assets/staffdock/portal/" : "/",
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    host: "staffdock.localhost",
    port: 8080,
    proxy: { "/api": frappe, "/assets": frappe },
  },
  build: {
    outDir: "../staffdock/public/portal",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "portal.js",
        chunkFileNames: "portal-[name]-[hash].js",
        assetFileNames: (asset) =>
          asset.names?.some((n) => n.endsWith(".css")) ? "portal.css" : "[name]-[hash][extname]",
      },
    },
  },
}));
