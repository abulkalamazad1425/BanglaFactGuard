import { defineConfig } from 'vite';
export default defineConfig({
  base: './',
  esbuild: { jsxFactory: 'h', jsxFragment: 'Fragment' },
  build: {
    rollupOptions: {
      input: { panel: 'index.html', background: 'src/background.js' },
      output: { entryFileNames: '[name].js', chunkFileNames: 'chunks/[name]-[hash].js' },
    },
  },
});
