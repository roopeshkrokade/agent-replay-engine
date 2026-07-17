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
    base: "./",
  };
});
