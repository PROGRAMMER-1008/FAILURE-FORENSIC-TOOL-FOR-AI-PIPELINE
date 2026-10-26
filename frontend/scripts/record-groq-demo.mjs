import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const output = path.resolve('../launch');
await mkdir(output, {recursive: true});
const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1280, height: 800}, recordVideo: {dir: path.join(output, 'raw'), size: {width: 1280, height: 800}}, reducedMotion: 'reduce'});
const page = await context.newPage();
const chapters = [];
let runId;
page.on('response', async response => {
  if (response.url().endsWith('/api/v1/runs') && response.request().method() === 'POST' && response.status() === 202) { runId = (await response.json()).id; }
});
const start = Date.now();
async function caption(title, text) {
  chapters.push({seconds: (Date.now() - start) / 1000, title, text});
  await page.evaluate(({title, text}) => {
    let panel = document.getElementById('recording-caption');
    if (!panel) { panel = document.createElement('div'); panel.id='recording-caption'; document.body.append(panel); }
    panel.style.cssText='position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#10162cf5;border-top:2px solid #b7a2ff;padding:16px 32px;color:#fff;font:16px system-ui;box-shadow:0 -8px 30px #0006;pointer-events:none';
    panel.replaceChildren();
    const heading=document.createElement('strong'); heading.textContent=title; heading.style.cssText='display:block;color:#cfbfff;font-size:20px;margin-bottom:5px';
    const line=document.createElement('span');line.textContent=text;panel.append(heading,line);
  }, {title,text});
}
async function show(locator, pause=4500) { await locator.evaluate(el => window.scrollTo({top: window.scrollY + el.getBoundingClientRect().top - 28, behavior: 'instant'})); await page.waitForTimeout(pause); }
try {
  await page.goto(process.env.FF_BROWSER_URL || 'http://127.0.0.1:18769');
  await page.getByRole('heading', {name:'Find where things went wrong.'}).waitFor();
  const config = await (await page.request.get(new URL('/api/v1/config', page.url()).href)).json();
  if(config.provider !== 'groq' || !config.ai_ready) throw new Error('A configured Groq instance is required');
  await caption('Failure Forensics | Real AI, visible evidence', 'A live Groq walkthrough using an invented invoice. No synthetic error injection.');
  await page.waitForTimeout(4500);
  await page.getByRole('link', {name:'+ New investigation'}).click();
  await page.getByRole('button', {name:'Load invented invoice'}).click();
  await caption('01 / Give the AI a document', 'The invoice says 814 EUR. The cloud provider processes this invented sample.');
  await show(page.locator('#source'), 5000);
  await page.getByRole('button', {name:'Queue investigation'}).click();
  await caption('02 / Watch the real pipeline run', 'Groq extracts facts, classifies the document and generates a summary.');
  await page.getByText('Execution finished.', {exact:false}).waitFor({timeout:180000});
  if (!runId) throw new Error('Missing submitted run ID');
  const run = await (await page.request.get(new URL(`/api/v1/runs/${runId}`, page.url()).href)).json();
  if (run.status !== 'succeeded' || run.attempts.length !== 3 || run.attempts.some(a => a.result.provider !== 'groq' || a.result.status !== 'succeeded')) throw new Error('The live Groq pipeline did not complete all three steps');
  await writeFile(path.join(output,'groq-run-evidence.json'), JSON.stringify(run,null,2));
  await caption('03 / Inspect the result before trusting it', 'Automated findings are suggestions. Compare the outputs against the original source.');
  await show(page.getByRole('region', {name:'Investigation summary'}), 5500);
  await caption('04 / Follow each dependency', 'Select a step to see its recorded AI output and execution evidence.');
  await show(page.locator('.pipeline-figure'), 5000);
  for (const name of ['Extract facts', 'Classify document', 'Summarize']) {
    await page.getByRole('button', {name:new RegExp(name)}).click();
    await caption(`Inspect / ${name}`, 'These are recorded Groq responses for this document, not fixed demo outputs.');
    await show(page.getByRole('heading', {name:'2. Check against the original'}), 6000);
  }
  await caption('05 / Keep human judgment explicit', 'Review the evidence, record uncertainty, and test corrections when appropriate.');
  await show(page.getByRole('heading', {name:'3. Record your review'}), 5000);
  await page.getByRole('button', {name:'Save review'}).click();
  await page.getByText('Review saved.', {exact:false}).waitFor();
  await page.getByRole('link', {name:'Overview',exact:true}).click();
  await caption('Failure Forensics | Built to investigate AI pipelines', `Live Groq model: ${config.producer_model}. One example is not an accuracy benchmark.`);
  await page.waitForTimeout(5000);
  await page.screenshot({path:path.join(output,'groq-video-cover.png')});
  await writeFile(path.join(output,'groq-demo-chapters.json'),JSON.stringify(chapters,null,2));
} finally {
  const video=page.video();
  await context.close();
  if(video) await video.saveAs(path.join(output,'failure-forensics-groq-demo.webm'));
  await browser.close();
}
console.log('Demo recording saved in launch/failure-forensics-groq-demo.webm');
