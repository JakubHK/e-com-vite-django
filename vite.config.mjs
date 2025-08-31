import { defineConfig } from vite;
import path from path;

export default defineConfig({
  root: .,
  base: /static/dist/,
  build: {
    manifest: true,
    outDir: path.resolve(static, dist),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: path.resolve(frontend, main.js),
      },
    },
  },
  server: {
    host: localhost,
    port: 5173,
    strictPort: true,
    origin: http://localhost:5173,
  },
});
