// @ts-check
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

// Served from GitHub Pages at https://dhananjaya-hbc.github.io/sinhala-news-corpus/
export default defineConfig({
  site: "https://dhananjaya-hbc.github.io",
  base: "/sinhala-news-corpus",
  trailingSlash: "always",
  build: {
    // The CSS is small (~8 KB); inlining it removes a render-blocking request
    inlineStylesheets: "always",
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
