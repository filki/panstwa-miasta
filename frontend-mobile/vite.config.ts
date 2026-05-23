import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  build: {
    outDir: 'www',  // Capacitor webDir
    emptyOutDir: true,
    target: 'es2022',
    sourcemap: true,
    rollupOptions: {
      input: 'index.html',
    },
  },
  server: {
    port: 5174,
    proxy: {
      '/ws': { target: 'http://localhost:8000', ws: true },
      '/api': { target: 'http://localhost:8000' },
    },
  },
});
