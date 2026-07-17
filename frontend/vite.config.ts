import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(async () => {
  const tailwindModule = await import("@tailwindcss/vite");
  const tailwind = tailwindModule.default ?? tailwindModule;

  return {
    plugins: [react(), tailwind()],
    build: {
      outDir: "dist",
      emptyOutDir: true,
    },
    // Proxy API requests during development to the backend server
    server: {
      proxy: {
        "/api": {
          target: "http://localhost:5000",
          changeOrigin: true,
          secure: false,
        },
      },
    },
    base: "./",
  };
});
