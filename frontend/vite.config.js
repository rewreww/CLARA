import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Development/demo routing. All backend/AI servers stay on loopback; browsers
// reach them only through the appropriate local Vite frontend.
function protectLocalAi() {
  return {
    name: 'clara-local-clinical-auth',
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        if (process.env.VITE_CLARA_AUTH_ENABLED !== 'true'
          || !request.url?.startsWith('/api/llm/')) return next()
        try {
          const verified = await fetch('http://127.0.0.1:5000/api/account/me', {
            headers: { cookie: request.headers.cookie || '' },
            signal: AbortSignal.timeout(3000),
          })
          if (verified.status === 200) {
            const profile = await verified.json()
            if (profile.role === 'clinician' || profile.role === 'trainee') return next()
            response.statusCode = 403
          } else response.statusCode = 401
        } catch {
          response.statusCode = 503
        }
        response.setHeader('Cache-Control', 'no-store')
        response.setHeader('Content-Type', 'application/json')
        response.end(JSON.stringify({ error: 'Authentication is required for CLARA AI.' }))
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), protectLocalAi()],
  server: {
    host: '127.0.0.1',
    port: 3000,
    strictPort: true,
    proxy: {
      '/api/llm': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/llm/, ''),
      },
      '/api/labs': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/labs/, ''),
      },
      '/api/backend': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/backend/, '/api'),
      },
    },
  },
})
