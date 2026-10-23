import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir, mkdtemp, rm } from 'node:fs/promises';
import { chromium } from 'playwright';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const html = process.env.APP_URL ? null : await readFile(`${process.argv[2]}/index.html`);
const server = createServer((req, res) => {
    if (req.method !== 'GET') { res.writeHead(405); res.end(); return; }
    res.setHeader('Content-Type', 'text/html'); res.end(html);
});
if (!process.env.APP_URL) await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const url = process.env.APP_URL || `http://127.0.0.1:${server.address().port}/`;
const launchOptions = { executablePath: process.env.CHROMIUM_PATH || '/usr/bin/chromium',
    headless: true, args: ['--disable-gpu', '--no-sandbox'] };
const browser = await chromium.launch(launchOptions);
const profile = await mkdtemp(join(tmpdir(), 'sdcpp-draft-test-'));
const persistentContexts = [];
const features = { ref_images: true, init_image: true, mask_image: true, control_image: true,
    ip_adapter: true, img2img: true, vae_tiling: true, cache: true, distilled_guidance: true,
    clip_skip: true, controlnet: true, high_noise: true, flow_shift: true, slg: true };
const recipe = { id: '@command-line', source: 'command_line', name: 'Example model', slots: [],
    defaults: { width: 512, height: 512, steps: 20, cfg_scale: 6 }, effective_features: features };
const draftRecipe = { id: 'example-recipe', source: 'builtin', name: 'Example draft recipe',
    slots: [{ id: 'diffusion_model', label: 'Diffusion model', required: true, category: 'diffusion_models' }],
    defaults: { width: 1280 }, effective_features: features };
const modelFiles = [{ id: 'diffusion_models/first.gguf', category: 'diffusion_models', name: 'first.gguf' },
    { id: 'diffusion_models/second.gguf', category: 'diffusion_models', name: 'second.gguf' }];
const runtime = { state: 'ready', origin: 'command_line', runtime_recipe: recipe, recipe: recipe.id, models: {} };
const defaults = { width: 512, height: 512, seed: -1, sample_params: { sample_method: 'euler',
    sample_steps: 20, guidance: { txt_cfg: 6 } }, vae_tiling_params: { enabled: true, tile_size_w: 256, tile_size_h: 256, target_overlap: 0.5 } };
const capabilities = { current_mode: 'img_gen', supported_modes: ['img_gen'], model: { name: 'example.gguf' },
    runtime, generation_features: features, defaults_by_mode: { img_gen: defaults },
    features_by_mode: { img_gen: { cancel_queued: true, cancel_generating: true } },
    samplers: ['euler', 'heun'], schedulers: ['flux', 'discrete'], preview_modes: ['none'],
    output_formats_by_mode: { img_gen: ['png', 'jpeg'] }, limits: { max_queue_size: 64 } };
let submissions = 0, jobStatus = 'generating', offline = false;
const job = () => ({ id: 'job_mock_1', kind: 'img_gen', status: jobStatus,
    created: Date.now() - 3000, started: Date.now() - 2000, completed: null, result: null });
async function mock(context) {
    await context.route('**/sdcpp/v1/**', async route => {
        const req = route.request(), path = new URL(req.url()).pathname;
        if (offline && path.endsWith('/capabilities')) return route.abort();
        let response;
        if (path.endsWith('/capabilities')) response = capabilities;
        else if (path.endsWith('/recipes')) response = { recipes: [draftRecipe], errors: [] };
        else if (path.endsWith('/model-files')) response = { files: modelFiles, errors: [] };
        else if (path.endsWith('/models/status')) response = runtime;
        else if (path.endsWith('/img_gen') && req.method() === 'POST') { submissions++; response = job(); }
        else if (path.endsWith('/jobs/job_mock_1/cancel')) { jobStatus = 'cancelled'; response = job(); }
        else if (path.endsWith('/jobs/job_mock_1')) response = job();
        else throw new Error(`Unexpected API access: ${req.method()} ${path}`);
        await route.fulfill({ json: response });
    });
}
function field(page, name) {
    return page.locator('.field').filter({ has: page.locator('label').filter({ hasText: new RegExp(`^${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`) }) }).locator('input, select').first();
}
async function check(page, prompt) {
    await page.waitForFunction(expected => document.querySelector('textarea')?.value === expected, prompt);
    assert.equal(await page.locator('textarea').nth(1).inputValue(), 'Keep natural texture.');
    for (const [name, expected] of [['Width','1024'], ['Height','768'], ['Steps','31'], ['CFG Scale','2.5'],
        ['Flow Shift','2.75'], ['Tile Width (px)','256'], ['Tile Height (px)','256'], ['Target Overlap','0.5']]) {
        assert.equal(await field(page, name).inputValue(), expected, name);
    }
    assert.equal(await page.locator('#image-seed').inputValue(), '43');
    assert.equal(await field(page, 'Method').inputValue(), 'heun');
    assert.equal(await page.locator('.file-chip__name').count(), 2);
    assert.equal(await page.getByRole('alert').count(), 0);
}
async function screenshot(page, name) {
    if (process.env.SCREENSHOT_DIR) {
        await mkdir(process.env.SCREENSHOT_DIR, { recursive: true });
        await page.screenshot({ path: `${process.env.SCREENSHOT_DIR}/${name}.png`, fullPage: true });
    }
}
try {
    const context = await chromium.launchPersistentContext(profile, { ...launchOptions, viewport: { width: 1440, height: 1100 } });
    persistentContexts.push(context);
    await mock(context);
    let page = await context.newPage();
    page.setDefaultTimeout(10000);
    await page.goto(url);
    await page.locator('#image-seed').waitFor();
    assert.equal(await page.locator('#image-seed').inputValue(), '-1');
    await page.locator('#model-recipe').click();
    await page.getByRole('option', { name: 'Example draft recipe · builtin' }).click();
    await page.locator('#model-slot-diffusion_model').click();
    await page.getByRole('option', { name: 'second.gguf', exact: true }).click();
    await field(page, 'Width').fill('896');
    await page.reload();
    await page.locator('#model-slot-diffusion_model').waitFor();
    assert.equal(await page.locator('#model-slot-diffusion_model').inputValue(), 'second.gguf');
    assert.equal(await field(page, 'Width').inputValue(), '896');
    await page.locator('#model-recipe').click();
    await page.getByRole('option', { name: 'Example model · command_line' }).click();
    console.log('PASS: recipe and model-file choices restore without reapplying defaults.');
    const prompt = 'A natural beach photograph. '.repeat(300) + 'Final keystroke: ✓';
    await page.locator('textarea').nth(0).fill(prompt);
    await page.locator('textarea').nth(1).fill('Keep natural texture.');
    await field(page, 'Width').fill('1024');
    await field(page, 'Height').fill('768');
    await page.locator('#image-seed').fill('43');
    await field(page, 'Method').selectOption('heun');
    await field(page, 'Steps').fill('31');
    await field(page, 'CFG Scale').fill('2.5');
    await field(page, 'Flow Shift').fill('2.75');
    await page.getByRole('button', { name: /^VAE Tiling/ }).click();
    await field(page, 'Tile Width (px)').fill('256');
    await field(page, 'Tile Height (px)').fill('256');
    await field(page, 'Target Overlap').fill('0.5');
    await page.getByRole('button', { name: /^Image Inputs/ }).click();
    const data = await page.evaluate(() => {
        const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1024;
        const ctx = canvas.getContext('2d'), pixels = ctx.createImageData(1024, 1024);
        let seed = 12345;
        for (let i = 0; i < pixels.data.length; i++) {
            seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
            pixels.data[i] = i % 4 === 3 ? 255 : seed >>> 24;
        }
        ctx.putImageData(pixels, 0, 0); return canvas.toDataURL('image/png').split(',')[1];
    });
    const refInput = page.locator('.upload-card').filter({ hasText: 'Reference Images' }).locator('input[type=file]');
    // Together these exceed localStorage's usual quota: image persistence must use IndexedDB.
    assert.ok(data.length * 2 > 5 * 1024 * 1024);
    await refInput.setInputFiles(['first.png', 'second.png'].map(name => ({ name, mimeType: 'image/png', buffer: Buffer.from(data, 'base64') })));
    await page.waitForFunction(async () => {
        const db = await new Promise(resolve => { const req = indexedDB.open('sdcpp-webui-drafts', 1); req.onsuccess = () => resolve(req.result); });
        const rows = await new Promise(resolve => { const req = db.transaction('images').objectStore('images').getAll(); req.onsuccess = () => resolve(req.result); });
        db.close(); return rows.some(row => row.ref_images?.length === 2);
    });
    const cookies = await context.cookies();
    const cookie = cookies.find(c => c.name === 'sdcpp-webui-draft');
    assert.equal(cookie.value.length, 32); assert.equal(cookie.sameSite, 'Lax'); assert.ok(cookie.expires > Date.now()/1000);
    await page.getByRole('button', { name: 'Refresh Server Info' }).click();
    await check(page, prompt);
    await page.reload();
    await check(page, prompt);
    await screenshot(page, 'restored-desktop');
    console.log('PASS: cookie, long prompts, settings, expanded sections and >5MiB of image data survive refresh and reload.');
    offline = true;
    await page.reload();
    await page.waitForFunction(expected => document.querySelector('textarea')?.value === expected, prompt);
    assert.equal(await page.locator('#image-seed').inputValue(), '43');
    offline = false;
    await page.getByRole('button', { name: 'Refresh Server Info' }).click(); await check(page, prompt);
    console.log('PASS: offline reload and reconnect preserve the draft.');
    await page.getByRole('button', { name: 'Generate Image', exact: true }).click();
    await page.getByRole('button', { name: 'Cancel', exact: true }).waitFor({ state: 'visible' });
    await page.reload(); await check(page, prompt);
    await page.getByRole('button', { name: 'Cancel', exact: true }).click();
    assert.equal(submissions, 1);
    await page.waitForFunction(() => document.body.textContent.includes('Job cancelled.'));
    console.log('PASS: reload resumes the existing job and enables cancellation without submitting another job.');
    await page.locator('.file-chip').first().getByRole('button', { name: 'Remove' }).click();
    await page.waitForFunction(async () => {
        const db = await new Promise(resolve => { const req = indexedDB.open('sdcpp-webui-drafts', 1); req.onsuccess = () => resolve(req.result); });
        const rows = await new Promise(resolve => { const req = db.transaction('images').objectStore('images').getAll(); req.onsuccess = () => resolve(req.result); });
        db.close(); return rows.some(row => row.ref_images?.length === 1);
    });
    await page.reload();
    await page.waitForFunction(() => document.querySelectorAll('.file-chip__name').length === 1);
    await page.close(); page = await context.newPage(); await page.goto(url);
    await page.locator('#image-seed').waitFor();
    assert.equal(await page.locator('textarea').first().inputValue(), prompt);
    assert.equal(await page.locator('.file-chip__name').count(), 1);
    console.log('PASS: image removal and reopening a tab retain the updated draft.');
    await page.setViewportSize({ width: 390, height: 844 });
    await screenshot(page, 'restored-mobile');
    await context.close();
    const reopened = await chromium.launchPersistentContext(profile, launchOptions);
    persistentContexts.push(reopened);
    await mock(reopened);
    const reopenedPage = await reopened.newPage(); await reopenedPage.goto(url);
    await reopenedPage.locator('#image-seed').waitFor();
    assert.equal(await reopenedPage.locator('textarea').first().inputValue(), prompt);
    assert.equal(await reopenedPage.locator('.file-chip__name').count(), 1);
    await reopened.close();
    console.log('PASS: closing and restarting the browser preserves cookies, form values and uploaded images.');
    const blocked = await browser.newContext(); await mock(blocked);
    await blocked.addInitScript(() => { Storage.prototype.setItem = () => { throw new DOMException('Storage blocked', 'QuotaExceededError'); }; });
    const blockedPage = await blocked.newPage(); await blockedPage.goto(url);
    await blockedPage.getByRole('alert').waitFor();
    await blockedPage.locator('textarea').first().fill('Typing still works.');
    assert.equal(await blockedPage.locator('textarea').first().inputValue(), 'Typing still works.');
    console.log('PASS: storage failure is visible and leaves the form usable.');
    await blocked.close();
} finally {
    for (const context of persistentContexts) await context.close();
    await browser.close();
    await rm(profile, { recursive: true });
    await new Promise(resolve => server.close(resolve));
}
