import { defineConfig } from 'vite';

// Indiginous is served from its canonical subpath. Deployments may still
// override this explicitly for local fixtures or a dedicated compatibility
// surface, but a plain build must not silently emit root-relative assets.
const base = process.env.VITE_BASE_PATH || '/indiginous/';

export default defineConfig({
  base,
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/ws': {
        target: 'ws://127.0.0.1:8765',
        ws: true,
      },
    },
  },
});
