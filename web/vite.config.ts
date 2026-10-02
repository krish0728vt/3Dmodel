import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The launcher sets SHAH_API_PROXY when it starts the dev server on a
// non-default backend port. Without it the proxy would keep targeting 8000 and
// silently talk to a different backend than the one just started.
const apiProxyTarget = process.env.SHAH_API_PROXY ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": apiProxyTarget
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Three.js is ~500 kB on its own and cannot be split usefully. It is
          // isolated here so it caches independently of application code and
          // so the viewer chunk reflects only our own code.
          three: ["three"]
        }
      }
    },
    // The `three` chunk is an irreducible vendor floor; it is lazy-loaded and
    // never part of the initial download. The limit sits just above it so the
    // warning still fires for a genuinely new regression instead of being
    // permanently noisy.
    chunkSizeWarningLimit: 560
  },
  test: {
    // The layout-structure suite reads workspace.css through `?raw` to assert
    // the no-scroll and spacing invariants. Vitest stubs CSS imports to an
    // empty string unless CSS handling is enabled.
    css: true
  }
});
