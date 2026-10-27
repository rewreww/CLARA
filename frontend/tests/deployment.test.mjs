import test from 'node:test'
import assert from 'node:assert/strict'
import middleware from '../middleware.js'

const vars = {
  CLARA_DEMO_ENABLED: 'true', CLARA_DEMO_USERNAME: 'respondent',
  CLARA_DEMO_PASSWORD: 'test-only-password-123456',
  CLARA_GATEWAY_KEY: 'test-only-gateway-key-12345678901234567890',
  CLARA_GATEWAY_URL: 'https://example.ngrok-free.app',
}
function run(path='/', headers={}, changes={}, method='GET') {
  for (const [key,value] of Object.entries({...vars,...changes})) process.env[key] = value
  return middleware(new Request(`https://clara.example${path}`, {method, headers}))
}
const auth = {authorization: `Basic ${Buffer.from('respondent:test-only-password-123456').toString('base64')}`}

test('closed or incomplete demo fails closed before serving HTML', () => {
  assert.equal(run('/',{}, {CLARA_DEMO_ENABLED:'false'}).status,503)
  assert.equal(run('/',auth, {CLARA_GATEWAY_KEY:''}).status,503)
  assert.equal(run('/',auth, {CLARA_GATEWAY_URL:'http://localhost:8080'}).status,503)
  assert.equal(run('/',auth, {CLARA_GATEWAY_URL:'https://host.example/other'}).status,503)
  assert.equal(run('/',auth, {CLARA_GATEWAY_URL:'https://REPLACE-WITH-YOUR-NGROK-DOMAIN'}).status,503)
})
test('all pages, assets, and APIs require respondent credentials', () => {
  for (const path of ['/', '/assets/app.js', '/api/backend/patientdata/patients']) {
    const result=run(path)
    assert.equal(result.status,401)
    assert.match(result.headers.get('www-authenticate'),/Basic/)
  }
  assert.equal(run('/',{authorization:'Basic !!!'}).status,401)
  assert.equal(run('/',auth).headers.get('x-middleware-next'),'1')
})
test('API rewrite keeps queries but replaces untrusted headers and credentials', () => {
  const result=run('/api/backend/patientdata/00001/document?source=discharge%2Freport.pdf', {
    ...auth, cookie:'private-cookie', 'x-clara-gateway-key':'attacker',range:'bytes=0-99',
  })
  assert.equal(result.headers.get('x-middleware-rewrite'), 'https://example.ngrok-free.app/api/backend/patientdata/00001/document?source=discharge%2Freport.pdf')
  assert.equal(result.headers.get('x-middleware-request-x-clara-gateway-key'),vars.CLARA_GATEWAY_KEY)
  assert.equal(result.headers.get('x-middleware-request-range'),'bytes=0-99')
  assert.equal(result.headers.get('x-middleware-request-authorization'),null)
  assert.equal(result.headers.get('x-middleware-request-cookie'),null)
  assert.equal(result.headers.get('cache-control'),'private, no-store')
})
test('cross-origin API calls and unrecognized service routes are denied', () => {
  assert.equal(run('/api/llm/chat/stream',{...auth,origin:'https://evil.example'}, {},'POST').status,403)
  assert.equal(run('/api/llm/chat/stream',{...auth,'sec-fetch-site':'cross-site'}, {},'POST').status,403)
  assert.equal(run('/api/arbitrary',auth).status,404)
  assert.equal(run('/api/llm/chat/stream',{...auth,origin:'https://clara.example'}, {},'POST').status,200)
})
test('Microsoft tunnel receives API forwarding header and private gateway key', () => {
  const result = run('/api/llm/chat/stream', auth, {CLARA_GATEWAY_URL:'https://test-8765.asse.devtunnels.ms'}, 'POST')
  assert.equal(result.headers.get('x-middleware-rewrite'),'https://test-8765.asse.devtunnels.ms/api/llm/chat/stream')
  assert.equal(result.headers.get('x-middleware-request-x-tunnel-skip-antiphishing-page'),'1')
  assert.equal(result.headers.get('x-middleware-request-x-clara-gateway-key'),vars.CLARA_GATEWAY_KEY)
  assert.equal(result.headers.get('x-middleware-request-ngrok-skip-browser-warning'),null)
})
