import { next, rewrite } from '@vercel/functions'

// This file runs on Vercel, never in the browser or the local Vite server.
export const config = { runtime: 'nodejs', matcher: '/:path*' }
const privateHeaders = {
  'Cache-Control': 'private, no-store',
  'X-Robots-Tag': 'noindex, nofollow, noarchive',
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
}

export default function middleware(request) {
  const { CLARA_DEMO_ENABLED,
    CLARA_GATEWAY_URL, CLARA_GATEWAY_KEY } = process.env
  if (CLARA_DEMO_ENABLED !== 'true') {
    return new Response('CLARA demo is closed. Please return during your scheduled evaluation.', { status: 503, headers: privateHeaders })
  }
  let gateway
  try {
    gateway = new URL(CLARA_GATEWAY_URL)
    if (gateway.protocol !== 'https:' || gateway.hostname.includes('replace-with') || gateway.username || gateway.password
      || gateway.pathname !== '/' || gateway.search || gateway.hash
      || !CLARA_GATEWAY_KEY || CLARA_GATEWAY_KEY.length < 32) throw new Error()
  } catch {
    return new Response('CLARA demo setup is incomplete. Please contact the research team.', { status: 503, headers: privateHeaders })
  }
  const url = new URL(request.url)
  if (url.pathname.startsWith('/api/')) {
    const origin = request.headers.get('origin')
    if ((origin && origin !== url.origin) || request.headers.get('sec-fetch-site') === 'cross-site') {
      return new Response('Cross-site API requests are not allowed.', { status: 403, headers: privateHeaders })
    }
    if (!/^\/api\/(llm|backend)\//.test(url.pathname)) {
      return new Response('Not found', { status: 404, headers: privateHeaders })
    }
    // A fresh allowlist prevents forwarding browser credentials/cookies or
    // client-supplied proxy/security headers to the tunnel.
    const headers = new Headers()
    for (const name of ['accept', 'content-type', 'range', 'if-range']) {
      if (request.headers.has(name)) headers.set(name, request.headers.get(name))
    }
    headers.set('x-clara-gateway-key', CLARA_GATEWAY_KEY)
    if (gateway.hostname.endsWith('.devtunnels.ms')) {
      headers.set('X-Tunnel-Skip-AntiPhishing-Page', '1')
    } else if (/\.(ngrok-free\.app|ngrok-free\.dev|ngrok\.app)$/.test(gateway.hostname)) {
      headers.set('ngrok-skip-browser-warning', '1')
    }
    gateway.pathname = url.pathname
    gateway.search = url.search
    return rewrite(gateway, { request: { headers }, headers: privateHeaders })
  }
  return next({ headers: privateHeaders })
}
