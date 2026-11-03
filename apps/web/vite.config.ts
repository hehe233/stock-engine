import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { componentLess } from './build/component-less';

export default defineConfig({
  plugins: [componentLess(), react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8001' },
  },
});
