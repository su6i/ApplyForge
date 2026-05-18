/**
 * Scrape data-related job statistics from France Travail / MétierScope
 * URL: candidat.francetravail.fr/metierscope/fiche-metier/{CODE}/{slug}
 *
 * Usage:
 *   node scripts/data_jobs_scraper.mjs
 *   DEBUG=1 node scripts/data_jobs_scraper.mjs   ← print raw page snippets
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const puppeteer = require('/Users/su6i/@-github/amir-cli/lib/nodejs/node_modules/puppeteer-core');
import fs from 'fs';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const BASE   = 'https://candidat.francetravail.fr/metierscope/fiche-metier';

// ROME codes from /docs/it_rome_codes.json; slugs derived from job names
const SEED_JOBS = [
    { code: 'M1405', slug: 'data-scientist',    name: 'Data Scientist' },
    { code: 'M1419', slug: 'data-analyst',      name: 'Data Analyst' },
    { code: 'M1811', slug: 'data-engineer',     name: 'Data Engineer' },
    { code: 'M1889', slug: 'ingenieur-ingenieure-en-intelligence-artificielle-ia', name: 'Ingénieur IA' },
    { code: 'M1872', slug: 'consultant-decisionnel-consultante-decisionnelle-business-intelligence', name: 'Consultant BI' },
    { code: 'M1868', slug: 'architecte-base-de-donnees', name: 'Architecte BDD' },
    { code: 'M1824', slug: 'developpeur-developpeusse-decisionnel-business-intelligence', name: 'Développeur BI' },
    { code: 'M1426', slug: 'chief-digital-officer-responsable-de-la-transformation-digitale', name: 'Chief Digital Officer' },
];

const delay = ms => new Promise(res => setTimeout(res, ms));

// Parse French number: "3 830" or "3 830" → 3830
// Accepts only digit + inline-space characters (no newline)
function parseNum(str) {
    if (!str) return 0;
    // Strip everything that is not a digit
    return parseInt(str.replace(/[^\d]/g, ''), 10) || 0;
}

// Extract the number immediately before a label on its own line
// e.g. "3 830\noffres d'emploi" → capture "3 830"
// We split lines and look for the label, then grab the preceding non-empty line
function extractBeforeLabel(text, labelPattern) {
    const lines = text.split('\n');
    for (let i = 1; i < lines.length; i++) {
        if (labelPattern.test(lines[i].trim())) {
            // Walk backwards to find the nearest non-empty line (the number)
            for (let j = i - 1; j >= 0; j--) {
                const candidate = lines[j].trim();
                if (candidate && /^\d/.test(candidate)) {
                    return candidate;
                }
                if (candidate && !/^\d/.test(candidate)) break; // hit non-number text
            }
        }
    }
    return null;
}

async function discoverFromSearch(page) {
    console.log('Discovering data jobs from MétierScope autocomplete...');
    try {
        await page.goto('https://candidat.francetravail.fr/metierscope/', {
            waitUntil: 'networkidle0', timeout: 20000
        });
        await delay(1200);

        // Find any visible text input
        const inputs = await page.$$('input');
        let typed = false;
        for (const inp of inputs) {
            const vis = await inp.evaluate(el => {
                const s = window.getComputedStyle(el);
                return s.display !== 'none' && s.visibility !== 'hidden' && el.offsetParent !== null;
            });
            if (vis) {
                await inp.click();
                await inp.type('data');
                typed = true;
                break;
            }
        }
        if (!typed) { console.log('  No visible input found'); return []; }
        await delay(2000);

        // Collect all links that reference /fiche-metier/CODE/slug
        const found = await page.evaluate(() =>
            Array.from(document.querySelectorAll('a[href*="fiche-metier"]')).map(a => {
                const m = (a.getAttribute('href') || '').match(/fiche-metier\/([A-Z]\d+)\/([^/?#\s]+)/);
                return m ? { code: m[1], slug: m[2], name: a.textContent.replace(/\s+/g, ' ').trim() } : null;
            }).filter(Boolean)
        );

        const seen = new Set();
        const unique = found.filter(j => seen.has(j.code) ? false : seen.add(j.code));
        if (unique.length) {
            console.log(`  Found ${unique.length} jobs: ${unique.map(j => `${j.code}(${j.name})`).join(', ')}`);
        } else {
            console.log('  No suggestions captured');
        }
        return unique;
    } catch (e) {
        console.log(`  Discovery error: ${e.message}`);
        return [];
    }
}

async function scrapeJob(page, code, slug, name) {
    const url = `${BASE}/${code}/${slug}`;
    try {
        await page.goto(url, { waitUntil: 'networkidle0', timeout: 20000 });
        await delay(800);

        // Click Statistiques tab if present
        const tabClicked = await page.evaluate(() => {
            const tab = Array.from(document.querySelectorAll('a, button, [role="tab"]'))
                .find(el => /statistiques/i.test(el.textContent.trim()));
            if (tab) { tab.click(); return true; }
            return false;
        });
        if (tabClicked) await delay(1500);

        const text = await page.evaluate(() => document.body.innerText);

        if (process.env.DEBUG) {
            ['demandeurs', 'offres', 'compris entre', 'CDI'].forEach(kw => {
                const idx = text.toLowerCase().indexOf(kw.toLowerCase());
                if (idx >= 0) console.log(`[DEBUG ${kw}]`, JSON.stringify(text.slice(Math.max(0, idx - 40), idx + 80)));
            });
        }

        // Numbers sit on their own line immediately before the label
        const offresStr     = extractBeforeLabel(text, /^offres d.emploi$/i);
        const demandeursStr = extractBeforeLabel(text, /^demandeurs d.emploi$/i);

        const offres     = parseNum(offresStr);
        const demandeurs = parseNum(demandeursStr);

        // Salary: "compris entre 2 232 € et 3 941 €"
        const salaryMatch = text.match(/compris entre\s+([\d][^\n€]*)\s*€\s*et\s+([\d][^\n€]*)\s*€/i);
        const salMin = salaryMatch ? parseNum(salaryMatch[1]) : null;
        const salMax = salaryMatch ? parseNum(salaryMatch[2]) : null;
        const salary = (salMin && salMax) ? `${salMin.toLocaleString('fr-FR')} – ${salMax.toLocaleString('fr-FR')} €` : 'N/A';

        // CDI: "CDI (31%)"
        const cdiMatch = text.match(/CDI\s*\((\d+)%\)/i);
        const cdi = cdiMatch ? `${cdiMatch[1]}%` : 'N/A';

        return { code, name, offres, demandeurs, salary, cdi };
    } catch (e) {
        console.error(`  ERROR ${code} ${name}: ${e.message}`);
        return { code, name, offres: 0, demandeurs: 0, salary: 'N/A', cdi: 'N/A', error: e.message };
    }
}

async function run() {
    const browser = await puppeteer.launch({
        executablePath: CHROME,
        headless: 'new',
        args: ['--no-sandbox']
    });
    const page = await browser.newPage();

    // Merge discovered jobs with seed list (seed wins on slug)
    const discovered = await discoverFromSearch(page);
    const map = new Map(SEED_JOBS.map(j => [j.code, j]));
    for (const j of discovered) {
        if (!map.has(j.code)) map.set(j.code, j);
    }
    const jobs = [...map.values()];

    console.log(`\nScraping ${jobs.length} jobs...\n`);
    const results = [];
    for (const job of jobs) {
        process.stdout.write(`  ${job.code}  ${job.name.padEnd(30)}...`);
        const r = await scrapeJob(page, job.code, job.slug, job.name);
        results.push(r);
        const ratio = r.offres > 0 ? (r.demandeurs / r.offres).toFixed(1) : '—';
        console.log(` offres=${r.offres}  dem.=${r.demandeurs}  ratio=${ratio}  ${r.salary}  CDI ${r.cdi}`);
        await delay(400);
    }

    await browser.close();
    results.sort((a, b) => b.offres - a.offres);

    const W = 92;
    console.log('\n' + '='.repeat(W));
    console.log('METIERS DATA — Marche national · France Travail / MétierScope · Mai 2026');
    console.log('='.repeat(W));
    console.log('Code'.padEnd(8) + 'Métier'.padEnd(32) + 'Offres'.padStart(8) + 'Demand.'.padStart(9) + 'Ratio'.padStart(7) + '  Salaire (80%)'.padEnd(22) + 'CDI');
    console.log('-'.repeat(W));
    for (const r of results) {
        if (!r.offres && !r.demandeurs) continue;
        const ratio = r.offres > 0 ? (r.demandeurs / r.offres).toFixed(1) : '—';
        const flag  = parseFloat(ratio) >= 3 ? ' ⚠' : '';
        console.log(
            r.code.padEnd(8) +
            r.name.padEnd(32) +
            String(r.offres).padStart(8) +
            String(r.demandeurs).padStart(9) +
            ratio.padStart(7) + flag.padEnd(3) + ' ' +
            r.salary.padEnd(22) +
            r.cdi
        );
    }

    const out = '/Users/su6i/@-github/CV/docs/data_jobs_stats.json';
    fs.writeFileSync(out, JSON.stringify({ scraped_at: new Date().toISOString(), source: 'France Travail / MétierScope', jobs: results }, null, 2));
    console.log(`\nSaved → ${out}`);
}

run().catch(console.error);
