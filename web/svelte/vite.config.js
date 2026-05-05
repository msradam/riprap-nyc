import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { resolve } from "path";

// Svelte 5 custom-element build → drop-in replacement for the Lit
// components in /web/static/components. agent.html keeps using
// <r-briefing>, <r-trace>, <r-sources-footer>; this bundle just
// supplies their implementation.
export default defineConfig({
  plugins: [
    svelte({
      compilerOptions: {
        // Globally compile every .svelte file as a custom element so we
        // get one bundle per page, no per-file flag needed.
        customElement: true,
      },
    }),
  ],
  build: {
    outDir: resolve(__dirname, "../static/dist"),
    emptyOutDir: true,
    lib: {
      entry: resolve(__dirname, "src/main.js"),
      formats: ["es"],
      fileName: () => "riprap.js",
    },
    rollupOptions: {
      output: { inlineDynamicImports: true },
    },
    target: "es2022",
    sourcemap: true,
  },
});
