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
  }
});
