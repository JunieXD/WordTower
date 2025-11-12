import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'
import Components from 'unplugin-vue-components/vite'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import fs from 'fs'
import path from 'path'

const keyPath = path.resolve(__dirname, 'localhost+2-key.pem')
const certPath = path.resolve(__dirname, 'localhost+2.pem')

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // vueDevTools(),
    tailwindcss(),
    AutoImport({
      imports: [
        'vue',
        {
          'naive-ui': ['useDialog', 'useMessage', 'useNotification', 'useLoadingBar'],
        },
      ],
    }),
    Components({
      resolvers: [NaiveUiResolver()],
    }),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['WTlogo.ico', 'WTlogo.png', 'WTlogo.svg', 'WTlogo-192.png', 'WTlogo-512.png'],
      manifest: {
        name: 'Word Tower',
        short_name: 'WordTower',
        description: 'Word Tower',
        theme_color: '#ffffff',
        background_color: '#ffffff',
        display: 'minimal-ui',
        orientation: 'portrait',
        scope: '/',
        start_url: '/',
        icons: [
          {
            src: '/WTlogo-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/WTlogo-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/.*\.(?:png|jpg|jpeg|svg|gif|webp)$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'images-cache',
              expiration: {
                maxEntries: 50,
                maxAgeSeconds: 60 * 60 * 24 * 30, // 30天
              },
            },
          },
          {
            urlPattern: /^https:\/\/.*\/api\/.*/i,
            handler: 'NetworkFirst',
            options: {
              cacheName: 'api-cache',
              expiration: {
                maxEntries: 50,
                maxAgeSeconds: 60 * 5, // 5分钟
              },
              networkTimeoutSeconds: 10,
            },
          },
        ],
      },
      devOptions: {
        enabled: true,
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
    https: {
      key: fs.readFileSync(keyPath),
      cert: fs.readFileSync(certPath),
    },
  },
})
