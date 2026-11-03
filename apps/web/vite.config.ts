import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { componentLess } from './build/component-less';
import { bundleReport } from './build/bundle-report';

export default defineConfig({
  plugins: [
    componentLess(),
    react(),
    ...(process.env.STOCK_BUNDLE_REPORT === '1'
      ? [bundleReport('../../.runtime/web-bundle-report.json')]
      : []),
  ],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8001' },
  },
});
