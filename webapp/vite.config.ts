import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
    "/external/promptflow": {
      target: "http://127.0.0.1:8080",
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/external\/promptflow/, ""),
    },"/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/external": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/opa-api": {
        target: "http://127.0.0.1:8181",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/opa-api/, ""),
      },
    },
  },
});
