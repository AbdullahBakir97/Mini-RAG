/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// In development the API runs separately (uvicorn or docker compose); these
// paths are forwarded to it, so the app always calls its own origin.
const api = process.env.API_URL ?? "http://localhost:8000";
const forwarded = ["/api", "/docs", "/openapi.json"];

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(forwarded.map((path) => [path, { target: api, changeOrigin: true }])),
  },
  test: {
    environment: "jsdom",
  },
});
