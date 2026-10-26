import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const output = path.resolve('../launch');
await mkdir(output, {recursive: true});
const browser = await chromium.launch();
const context = await browser.newContext({viewport: {width: 1280, height: 800}, recordVideo: {dir: path.join(output, 'raw'), size: {width: 1280, height: 800}}, reducedMotion: 'reduce'});
const page = await context.newPage();
const chapters = [];
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
  await page.goto(process.env.FF_BROWSER_URL || 'http://127.0.0.1:18767');
  await page.getByRole('heading', {name:'Find where things went wrong.'}).waitFor();
  await caption('Failure Forensics | Trace the mistake, not just the final answer', 'A real app walkthrough using an invented invoice and a deliberately injected error.');
  await page.waitForTimeout(5000);
  await page.getByRole('link', {name:'+ New investigation'}).click();
  await page.getByRole('button', {name:'Load invented invoice'}).click();
  await caption('01 / Start with a document', 'The source says 814 EUR. This synthetic example deliberately extracts 999 EUR.');
  await show(page.locator('#source'), 5500);
  await page.getByRole('button', {name:'Queue investigation'}).click();
  await page.getByText('Execution finished.', {exact:false}).waitFor({timeout:30000});
  await caption('02 / A finished run can still contain a wrong answer', 'Processing status and content quality are kept separate. Findings remain hypotheses.');
  await show(page.getByRole('region', {name:'Investigation summary'}), 5000);
  await caption('03 / Follow the actual dependencies', 'Extraction and classification branch independently. The summary uses both and the source.');
  await show(page.locator('.pipeline-figure'), 6000);
  await page.getByRole('button', {name:/Extract facts/}).click();
  await caption('04 / Compare evidence with the output', 'Source: 814 EUR. Extracted fact: 999 EUR. The suspected starting point is visible.');
  await show(page.getByRole('heading', {name:'2. Check against the original'}), 6500);
  await caption('05 / Human review stays in control', 'Confirm, correct or mark a finding as uncertain. No label is silently treated as ground truth.');
  await page.getByRole('combobox', {name:/Verdict/}).selectOption('confirm');
  await page.getByRole('checkbox', {name:'Fact extraction',exact:true}).check();
  await show(page.getByRole('heading', {name:'3. Record your review'}), 4500);
  await page.getByRole('button', {name:'Save review'}).click();
  await page.getByText('Review saved.', {exact:false}).waitFor();
  await caption('06 / Change one fact, then test the result', 'Correct 999 to 814 using a normal input. Keep the original run intact.');
  await page.getByRole('button', {name:'Copy facts to edit'}).click();
  const field=page.getByLabel(/Corrected value 1/);
  await field.fill('814 EUR');
  await show(field, 5000);
  await page.getByRole('button', {name:'Run with my correction'}).click();
  await page.getByRole('heading', {name:'Original versus replay'}).waitFor({timeout:30000});
  await caption('07 / Inspect what changed', 'The replay updates affected steps. A changed result is evidence to investigate, not proof of causality.');
  await show(page.getByRole('heading', {name:'Original versus replay'}), 6500);
  await page.getByRole('link', {name:'Review dataset',exact:true}).click();
  await caption('08 / Turn reviewed examples into repeatable evaluation', 'Save reviewed cases in versioned datasets. The demo measures mechanics, not real-model accuracy.');
  await page.waitForTimeout(5000);
  await page.getByRole('link', {name:'Overview',exact:true}).click();
  await caption('Built with React, TypeScript, FastAPI and SQLAlchemy', 'Groq / local Ollama adapters • durable tracing • evidence review • controlled replay');
  await page.waitForTimeout(5500);
  await page.screenshot({path:path.join(output,'video-cover.png')});
  await writeFile(path.join(output,'demo-chapters.json'),JSON.stringify(chapters,null,2));
} finally {
  const video=page.video();
  await context.close();
  if(video) await video.saveAs(path.join(output,'failure-forensics-demo.webm'));
  await browser.close();
}
console.log('Demo recording saved in launch/failure-forensics-demo.webm');
