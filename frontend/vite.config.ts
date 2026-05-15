import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendPort = Number.parseInt(process.env.CSP_PORT ?? "8000", 10);
const resolvedBackendPort =
  Number.isFinite(backendPort) && backendPort > 0 && backendPort <= 65535 ? backendPort : 8000;
const backendTarget = `http://127.0.0.1:${resolvedBackendPort}`;

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
      },
      "/covers": {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
});
