const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const BASE_URL = 'http://127.0.0.1:5055';
const OUT_DIR = process.env.OUT_DIR ? path.resolve(process.env.OUT_DIR) : path.resolve(__dirname, '../docs/ui-baseline');

if (!fs.existsSync(OUT_DIR)) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
}

let PAGES = [
  { name: 'home', path: '/home' },
  { name: 'dashboard', path: '/dashboard' },
  { name: 'pipeline', path: '/pipeline' },
  { name: 'leads', path: '/leads' },
  { name: 'lead_detail', path: '/leads/1' },
  { name: 'clients', path: '/clients' },
  { name: 'client_detail', path: '/clients/1' },
  { name: 'whatsapp_inbox', path: '/whatsapp' },
  { name: 'prospecting_dashboard', path: '/prospecting/dashboard' },
  { name: 'prospecting_campaigns', path: '/prospecting/campaigns' },
  { name: 'prospecting_messages', path: '/prospecting/messages' },
  { name: 'financial', path: '/financial' },
  { name: 'financial_strategic', path: '/financial/strategic' },
  { name: 'financial_payable', path: '/financial/payable' },
  { name: 'tasks', path: '/tasks/' },
  { name: 'contracts', path: '/contracts' },
  { name: 'settings', path: '/settings/company' },
  { name: 'master_companies', path: '/master/dashboard' },
];

if (process.env.FILTER_PAGES) {
  const allowed = process.env.FILTER_PAGES.split(',').map(s => s.trim());
  PAGES = PAGES.filter(p => allowed.includes(p.name));
}

async function captureAll() {
  console.log('🚀 Starting screenshot capture...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  try {
    const page = await browser.newPage();

    // --- 1. CAPTURE LOGINS BEFORE AUTHENTICATION ---
    console.log('📸 Capturing Login views...');
    await page.setViewport({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await new Promise(r => setTimeout(r, 800));
    await page.screenshot({ path: path.join(OUT_DIR, 'desktop_login.png'), fullPage: false });
    console.log('  ✅ desktop_login.png');

    await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
    await new Promise(r => setTimeout(r, 400));
    await page.screenshot({ path: path.join(OUT_DIR, 'mobile_login.png'), fullPage: false });
    console.log('  ✅ mobile_login.png');

    // --- 2. AUTHENTICATE ---
    console.log('🔑 Performing Login...');
    await page.setViewport({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForSelector('input[name="email"]', { timeout: 10000 });
    await page.type('input[name="email"]', 'Admin@northway.com.br');
    await page.type('input[name="password"]', 'admin123');
    await Promise.all([
      page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 30000 }),
      page.click('button[type="submit"]')
    ]);
    console.log('  ✅ Logged in successfully');

    await page.evaluateOnNewDocument(() => {
      try { sessionStorage.setItem('northway_welcome_shown', 'true'); } catch (e) {}
    });

    // --- 3. DESKTOP CAPTURES ---
    console.log('📸 Capturing Desktop views (1440px)...');
    await page.setViewport({ width: 1440, height: 900 });
    for (const p of PAGES) {
      try {
        await page.goto(`${BASE_URL}${p.path}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.evaluate(() => {
          const splash = document.getElementById('splash-screen');
          if (splash) splash.style.display = 'none';
        });
        await new Promise(r => setTimeout(r, 1000));
        await page.screenshot({ path: path.join(OUT_DIR, `desktop_${p.name}.png`), fullPage: false });
        console.log(`  ✅ desktop_${p.name}.png`);
      } catch (err) {
        console.error(`  ❌ Failed desktop_${p.name}:`, err.message);
      }
    }

    // --- 4. MOBILE CAPTURES ---
    console.log('📱 Capturing Mobile views (390px)...');
    await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true });
    for (const p of PAGES) {
      try {
        await page.goto(`${BASE_URL}${p.path}`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.evaluate(() => {
          const splash = document.getElementById('splash-screen');
          if (splash) splash.style.display = 'none';
        });
        await new Promise(r => setTimeout(r, 1000));
        await page.screenshot({ path: path.join(OUT_DIR, `mobile_${p.name}.png`), fullPage: false });
        console.log(`  ✅ mobile_${p.name}.png`);
      } catch (err) {
        console.error(`  ❌ Failed mobile_${p.name}:`, err.message);
      }
    }

    console.log('🎉 All baseline screenshots captured successfully!');
  } finally {
    await browser.close();
  }
}

captureAll().catch(err => {
  console.error('Fatal error during capture:', err);
  process.exit(1);
});
