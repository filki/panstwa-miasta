import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    target: 'es2022',
    sourcemap: true,
    rollupOptions: {
      input: 'index.html',
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/ws': { target: 'http://localhost:8000', ws: true },
      '/api': { target: 'http://localhost:8000' },
    },
  },
});
