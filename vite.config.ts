/**
 * Copyright (c) 2025 Cade Russell
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

// @ts-expect-error process is a nodejs global
const host = process.env.TAURI_DEV_HOST;

// https://vite.dev/config/
export default defineConfig(async () => ({
  plugins: [react()],

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  server: {
    port: 1425,
    strictPort: true,
    allowedHosts: [process.env.VITE_ALLOWED_HOSTS || "localhost"],
    host: host || false,
    hmr: host
      ? {
        protocol: "ws",
        host,
        port: 1421,
      }
      : undefined,
    watch: {
      // 3. tell Vite to ignore watching `src-tauri`
      ignored: ["**/src-tauri/**"],
    },
    // Proxy API requests to backend server
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8780',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 2500,
    rollupOptions: {
      output: {
        // Function form (not object form): shared transitive deps must be
        // placed deterministically. With the object form, "scheduler"
        // (shared by react-dom and @react-three/fiber's react-reconciler)
        // landed inside vendor-3d, creating a circular chunk
        // (vendor-3d <-> vendor-react) that made the app shell eagerly load
        // the entire 1MB+ 3D bundle at startup.
        manualChunks(id: string) {
          // Shared helper modules (rollup commonjs helpers, babel runtime
          // helpers) are imported by nearly every chunk; without a pin they
          // can get colored into a heavy lazy vendor chunk, forcing eager
          // loads of it. vendor-react always loads first, so they are free
          // there. (Other \0 virtual modules — e.g. commonjs proxies — must
          // fall through so they follow their owning package.)
          if (
            id.includes("commonjsHelpers") ||
            id.includes("vite/preload-helper") ||
            id.includes("vite/modulepreload-polyfill")
          ) {
            return "vendor-react";
          }
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("node_modules/@babel/runtime/") || id.includes("node_modules\\@babel\\runtime\\")) {
            return "vendor-react";
          }
          const has = (pkg: string) =>
            id.includes(`node_modules/${pkg}/`) || id.includes(`node_modules\\${pkg}\\`);

          // 3D stack — lazy, loads only on the /spatial route.
          if (
            has("three") ||
            has("@react-three") ||
            has("react-reconciler") ||
            has("its-fine")
          ) {
            return "vendor-3d";
          }
          // zustand is shared by reactflow (2D) and the spatial stores (3D):
          // it gets its own tiny chunk so neither side drags the other in.
          if (has("zustand")) return "vendor-state";
          if (has("reactflow") || has("@reactflow")) return "vendor-flow";
          if (has("lucide-react")) return "vendor-icons";
          if (has("jspdf") || has("html2canvas") || has("html2canvas-oklch") || has("jszip")) {
            return "vendor-export";
          }
          if (has("katex")) return "vendor-math";
          if (
            has("react") ||
            has("react-dom") ||
            has("react-router") ||
            has("react-router-dom") ||
            has("scheduler") ||
            has("@tanstack")
          ) {
            return "vendor-react";
          }
          return undefined;
        },
      },
    },
  },
}));
