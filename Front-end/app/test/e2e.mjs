/* E2E acceptance: multi-viewport screenshots + interaction checks.
   Uses system Microsoft Edge via puppeteer-core (no Chromium download). */
import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { existsSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import puppeteer from 'puppeteer-core'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const SHOTS = path.join(ROOT, 'test', 'shots')
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const URL_ = 'http://localhost:5173'
mkdirSync(SHOTS, { recursive: true })

const FIXTURE = path.join(ROOT, 'test', 'fixtures', 'zhang-san-resume.pdf')
mkdirSync(path.dirname(FIXTURE), { recursive: true })
writeFileSync(FIXTURE, '%PDF-1.4 fake resume fixture for upload test\n')

const VIEWPORTS = [
  { name: 'desktop-1920x1080', width: 1920, height: 1080 },
  { name: 'desktop-1440x900', width: 1440, height: 900 },
  { name: 'tablet-768x1024', width: 768, height: 1024 },
  { name: 'mobile-390x844', width: 390, height: 844 },
]

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function waitForServer(timeoutMs = 30000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(URL_)
      if (res.ok) return true
    } catch { /* not up yet */ }
    await sleep(400)
  }
  return false
}

const server = spawn(process.execPath, [path.join(ROOT, 'node_modules', 'vite', 'bin', 'vite.js'), '--port', '5173', '--strictPort'], {
  cwd: ROOT,
  stdio: ['ignore', 'pipe', 'pipe'],
})
server.stdout.on('data', () => {})
server.stderr.on('data', (d) => process.stderr.write(d))

const report = { consoleErrors: [], pageErrors: [], viewports: {}, interactions: {} }

try {
  if (!(await waitForServer())) throw new Error('dev server did not start')
  const browser = await puppeteer.launch({
    executablePath: EDGE,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--force-device-scale-factor=1'],
  })

  for (const vp of VIEWPORTS) {
    const page = await browser.newPage()
    await page.setViewport({ width: vp.width, height: vp.height })
    page.on('console', (msg) => {
      if (msg.type() === 'error') report.consoleErrors.push(`[${vp.name}] ${msg.text()}`)
    })
    page.on('pageerror', (err) => report.pageErrors.push(`[${vp.name}] ${err.message}`))
    await page.goto(URL_, { waitUntil: 'networkidle0' })
    await sleep(400)

    const metrics = await page.evaluate(() => {
      const de = document.documentElement
      return {
        scrollWidth: de.scrollWidth,
        clientWidth: de.clientWidth,
        scrollHeight: de.scrollHeight,
        clientHeight: de.clientHeight,
        horizontalOverflow: de.scrollWidth > de.clientWidth,
        sectionRect: document.querySelector('.upload-section')?.getBoundingClientRect().toJSON(),
      }
    })
    await page.screenshot({ path: path.join(SHOTS, `${vp.name}.png`), fullPage: true })
    report.viewports[vp.name] = metrics
    await page.close()
  }

  // ---- interaction tests at desktop size ----
  const page = await browser.newPage()
  await page.setViewport({ width: 1920, height: 1080 })
  page.on('pageerror', (err) => report.pageErrors.push(`[interactions] ${err.message}`))
  page.on('console', (msg) => {
    if (msg.type() === 'error') report.consoleErrors.push(`[interactions] ${msg.text()}`)
  })
  await page.goto(URL_, { waitUntil: 'networkidle0' })

  // 1. click dropzone -> file chooser -> file name displayed
  const [chooser] = await Promise.all([
    page.waitForFileChooser({ timeout: 5000 }),
    page.click('.dropzone'),
  ])
  await chooser.accept([FIXTURE])
  await sleep(300)
  const fileNameShown = await page.$eval('.dropzone__file-name', (el) => el.textContent)
  report.interactions.fileNameAfterSelect = fileNameShown
  await page.screenshot({ path: path.join(SHOTS, 'interaction-file-selected.png') })

  // 2. hover state on primary button
  await page.hover('.btn--primary')
  await sleep(250)
  await page.screenshot({ path: path.join(SHOTS, 'interaction-hover-primary.png') })
  const hoverBg = await page.$eval('.btn--primary', (el) => getComputedStyle(el).backgroundColor)
  report.interactions.primaryHoverBg = hoverBg

  // 3. active state (pressed) with real mouse events
  await page.hover('.btn--primary')
  await page.mouse.down()
  await sleep(150)
  const activeBg = await page.$eval('.btn--primary', (el) => getComputedStyle(el).backgroundColor)
  await page.mouse.up()
  report.interactions.primaryActiveBg = activeBg

  // 4. keyboard: on a fresh page, Tab focuses dropzone, Enter opens file chooser
  await page.reload({ waitUntil: 'networkidle0' })
  await sleep(300)
  await page.keyboard.press('Tab')
  let focusedTag = await page.evaluate(() => {
    const el = document.activeElement
    return el ? `${el.tagName}.${el.className}` : 'none'
  })
  if (!focusedTag.includes('dropzone')) {
    await page.keyboard.press('Tab')
    focusedTag = await page.evaluate(() => {
      const el = document.activeElement
      return el ? `${el.tagName}.${el.className}` : 'none'
    })
  }
  report.interactions.keyboardFocus = focusedTag
  try {
    const [chooser2] = await Promise.all([
      page.waitForFileChooser({ timeout: 5000 }),
      page.keyboard.press('Enter'),
    ])
    await chooser2.accept([FIXTURE])
    await sleep(200)
    report.interactions.keyboardEnterOpensDialog = true
  } catch (e) {
    report.interactions.keyboardEnterOpensDialog = `failed: ${e.message.slice(0, 80)}`
  }

  // 5. mobile layout: stacked direction
  await page.setViewport({ width: 390, height: 844 })
  await sleep(400)
  const stacked = await page.evaluate(() => {
    const section = document.querySelector('.upload-section')
    return getComputedStyle(section).flexDirection
  })
  const introTop = await page.evaluate(() => document.querySelector('.intro').getBoundingClientRect().top)
  const cardTop = await page.evaluate(() => document.querySelector('.card').getBoundingClientRect().top)
  report.interactions.mobileFlexDirection = stacked
  report.interactions.mobileStackedOrderCorrect = introTop < cardTop
  await page.screenshot({ path: path.join(SHOTS, 'mobile-stacked-check.png'), fullPage: true })

  await browser.close()
} finally {
  writeFileSync(path.join(ROOT, 'test', 'report.json'), JSON.stringify(report, null, 2))
  console.log(JSON.stringify(report, null, 2))
  server.kill()
}
