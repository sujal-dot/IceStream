/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const isHtmlRequest = (req: any) => {
  return req.headers && req.headers.accept && req.headers.accept.includes('text/html');
};

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/lineage': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
        bypass: (req) => (isHtmlRequest(req) ? '/index.html' : undefined),
      },
      '/pipeline': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
        bypass: (req) => (isHtmlRequest(req) ? '/index.html' : undefined),
      },
      '/metrics': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
        bypass: (req) => (isHtmlRequest(req) ? '/index.html' : undefined),
      },
      '/quality': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
        bypass: (req) => (isHtmlRequest(req) ? '/index.html' : undefined),
      },
      '/incidents': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
        bypass: (req) => (isHtmlRequest(req) ? '/index.html' : undefined),
      },
      '/schema': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
        bypass: (req) => (isHtmlRequest(req) ? '/index.html' : undefined),
      },
      '/events': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
        bypass: (req) => (isHtmlRequest(req) ? '/index.html' : undefined),
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
});
