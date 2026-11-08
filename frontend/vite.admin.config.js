import { defineConfig } from 'vite'
import baseConfig from './vite.config.js'

// Admin is intentionally the only Vite frontend reachable on the hospital demo LAN.
// The clinical Vite server remains bound to 127.0.0.1:3000.
export default defineConfig({
  ...baseConfig,
  plugins: [
    ...(baseConfig.plugins || []),
    {
      name: 'clara-admin-home',
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url === '/' || req.url?.startsWith('/?')) req.url = '/admin.html'
          next()
        })
      },
    },
  ],
  server: { ...baseConfig.server, host: '0.0.0.0', port: 3001, strictPort: true },
})
