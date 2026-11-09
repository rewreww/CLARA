import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const asset = relative => readFileSync(fileURLToPath(new URL(relative, import.meta.url)), 'utf8')

test('CLARA icon is provided as a scalable branded asset', () => {
  const svg = asset('../public/clara-mark.svg')
  assert.match(svg, /<svg[^>]+viewBox="0 0 670 560"/)
  assert.match(svg, /linearGradient/)
  assert.match(svg, /spark-gradient/)
})

test('browser favicon and welcome logo reuse the same asset', () => {
  const html = asset('../index.html')
  const chat = asset('../src/components/ChatPanel.jsx')
  assert.match(html, /rel="icon"[^>]+href="\/clara-mark\.svg"/)
  assert.match(chat, /className="clara-welcome-logo"[^>]+src="\/clara-mark\.svg"/)
})

test('left navigation uses text wordmark without the old activity icon', () => {
  const sidebar = asset('../src/components/WorkspaceSidebar.jsx')
  assert.doesNotMatch(sidebar, /<Activity\b/)
  assert.match(sidebar, /sidebar-brand-identity/)
})
