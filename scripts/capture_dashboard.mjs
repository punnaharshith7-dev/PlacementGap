import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

const edge = process.env.EDGE_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const port = 9333
const output = resolve('docs/eval-dashboard.png')
const email = 'placementgap-screenshot-' + Date.now() + '-' + Math.random().toString(16).slice(2) + '@example.com'
const phone = '+1 202 555 ' + String(Date.now()).slice(-4)
const signupResponse = await fetch('http://127.0.0.1:8000/auth/signup', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    full_name: 'PlacementGap Screenshot',
    email,
    phone,
    password: 'screenshot-only-password',
  }),
})
if (!signupResponse.ok) throw new Error('Could not prepare a local screenshot session (' + signupResponse.status + ')')
const challenge = await signupResponse.json()
if (!challenge.development_code) throw new Error('Screenshot capture requires the local development OTP mode')
const verifyResponse = await fetch('http://127.0.0.1:8000/auth/verify', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ challenge_id: challenge.challenge_id, code: challenge.development_code }),
})
if (!verifyResponse.ok) throw new Error('Could not verify the local screenshot session (' + verifyResponse.status + ')')
const cookieHeader = verifyResponse.headers.getSetCookie?.()[0] ?? verifyResponse.headers.get('set-cookie')
const session = cookieHeader?.match(/placementgap_session=([^;]+)/)?.[1]
if (!session) throw new Error('The local API did not set the PlacementGap session cookie')

const browser = spawn(edge, [
  '--headless=new',
  '--disable-gpu',
  '--hide-scrollbars',
  '--window-size=1600,1300',
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${resolve('data/dashboard-screenshot-profile')}`,
  'http://127.0.0.1:5173/',
], { stdio: 'ignore', windowsHide: true })

let socket
try {
  let page
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json`)
      const targets = await response.json()
      page = targets.find((target) => target.type === 'page' && target.url.startsWith('http://127.0.0.1:5173/'))
      if (page) break
    } catch {
      await new Promise((done) => setTimeout(done, 250))
    }
  }
  if (!page) throw new Error('Edge did not open the local PlacementGap page')

  socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolveOpen, reject) => {
    socket.addEventListener('open', resolveOpen, { once: true })
    socket.addEventListener('error', reject, { once: true })
  })
  let nextId = 0
  const pending = new Map()
  socket.addEventListener('message', (event) => {
    const message = JSON.parse(event.data)
    if (!message.id) return
    const item = pending.get(message.id)
    if (!item) return
    pending.delete(message.id)
    if (message.error) item.reject(new Error(message.error.message))
    else item.resolve(message.result)
  })
  const send = (method, params = {}) => new Promise((resolveCall, reject) => {
    const id = ++nextId
    pending.set(id, { resolve: resolveCall, reject: reject })
    socket.send(JSON.stringify({ id, method, params }))
  })

  await send('Page.enable')
  await send('Runtime.enable')
  await send('Network.enable')
  await send('Network.setCookie', {
    name: 'placementgap_session',
    value: session,
    url: 'http://127.0.0.1:5173/',
    httpOnly: true,
    sameSite: 'Lax',
  })
  await send('Emulation.setDeviceMetricsOverride', {
    width: 1600, height: 1300, deviceScaleFactor: 1, mobile: false,
  })
  let ready = false
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const status = await send('Runtime.evaluate', { expression: 'document.readyState', returnByValue: true })
    if (status.result.value === 'complete') { ready = true; break }
    await new Promise((done) => setTimeout(done, 250))
  }
  if (!ready) throw new Error('The local app page did not finish loading')
  await send('Page.navigate', { url: 'http://127.0.0.1:5173/dashboard' })
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const dashboard = await send('Runtime.evaluate', {
      expression: 'document.body.innerText',
      returnByValue: true,
    })
    if (dashboard.result.value.includes('Overview') && dashboard.result.value.includes('Analyze')) break
    await new Promise((done) => setTimeout(done, 250))
  }
  const clicked = await send('Runtime.evaluate', {
    expression: `(() => {
      const button = [...document.querySelectorAll('button')].find(item => item.textContent.includes('Evals'));
      if (!button) return false;
      button.click();
      return true;
    })()`, returnByValue: true,
  })
  if (!clicked.result.value) throw new Error('Could not find the Evals navigation control')
  let visibleText
  for (let attempt = 0; attempt < 60; attempt += 1) {
    visibleText = await send('Runtime.evaluate', {
      expression: 'document.body.innerText', returnByValue: true,
    })
    if (visibleText.result.value.includes('Evaluation dashboard')
      && visibleText.result.value.includes('Ablation results')
      && !visibleText.result.value.includes('Loading evaluation metrics')) break
    await new Promise((done) => setTimeout(done, 250))
  }
  if (!visibleText.result.value.includes('Evaluation dashboard') || !visibleText.result.value.includes('Ablation results')) {
    throw new Error(`The evaluation dashboard did not finish loading from the live API: ${visibleText.result.value.slice(0, 1200)}`)
  }
  const emailLiteral = JSON.stringify(email)
  await send('Runtime.evaluate', {
    expression: "(() => { const emailNode = document.querySelector('.signed-in-card small'); if (emailNode && emailNode.textContent.trim() === " + emailLiteral + ") emailNode.textContent = 'demo@placementgap.test' })()",
  })
  const { contentSize } = await send('Page.getLayoutMetrics')
  const shot = await send('Page.captureScreenshot', {
    format: 'png', fromSurface: true, captureBeyondViewport: true,
    clip: { x: 0, y: 0, width: Math.ceil(contentSize.width), height: Math.ceil(contentSize.height), scale: 1 },
  })
  await mkdir(resolve('docs'), { recursive: true })
  await writeFile(output, Buffer.from(shot.data, 'base64'))
  console.log(`Captured ${output}`)
} finally {
  if (socket?.readyState === WebSocket.OPEN) socket.close()
  browser.kill()
}
