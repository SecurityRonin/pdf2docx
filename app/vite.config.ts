import { defineConfig } from "vite";

// Tauri expects a fixed port and must not clear the terminal on error.
export default defineConfig({
  clearScreen: false,
  server: { port: 1420, strictPort: true },
  build: { target: "es2021", outDir: "dist", emptyOutDir: true },
});
