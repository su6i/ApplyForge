import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const puppeteer = require('/Users/su6i/@-github/amir-cli/lib/nodejs/node_modules/puppeteer-core');
import fs from 'fs';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const romes = [
    { code: 'M1805', name: 'Développement informatique' },
    { code: 'M1827', name: 'Ingénieur DevOps' },
    { code: 'M1802', name: 'Expertise & support SI' },
    { code: 'M1810', name: 'Production & exploitation SI' },
    { code: 'M1806', name: 'Conseil & MOA SI' },
    { code: 'M1801', name: 'Administration SI' },
    { code: 'M1821', name: 'Data Scientist / Analyst' },
    { code: 'M1826', name: 'Expert Cyber-sécurité' },
];

const depts = [
    { code: 'FR', name: 'National', type: 'NAT' },
    { code: '75', name: 'Paris (75)', type: 'DEP' },
    { code: '69', name: 'Lyon (69)', type: 'DEP' },
    { code: '13', name: 'Marseille (13)', type: 'DEP' },
    { code: '31', name: 'Toulouse (31)', type: 'DEP' },
    { code: '44', name: 'Nantes (44)', type: 'DEP' },
    { code: '33', name: 'Bordeaux (33)', type: 'DEP' },
    { code: '59', name: 'Lille (59)', type: 'DEP' },
    { code: '69', name: 'Lyon (69)', type: 'DEP' },
];

const delay = ms => new Promise(res => setTimeout(res, ms));

async function scrapeRome(page, dept, rome) {
    const url = `https://dataemploi.francetravail.fr/emploi/metier/chiffres-cles/${dept.type}/${dept.code}/${rome.code}`;
    try {
        await page.goto(url, { waitUntil: 'networkidle0', timeout: 15000 });
        await delay(500);
        const text = await page.evaluate(() => document.body.innerText);

        // Page format: "Offres d'emploi\n\n52,510\n\ndiffusées"
        const extractNum = str => str ? parseInt(str.replace(/,/g, ''), 10) || 0 : 0;
        const oMatch   = text.match(/Offres d.emploi\n+([\d,]+)\n+diffus/i);
        const dMatch   = text.match(/Demandeurs d.emploi\n+([\d,]+)\n+inscrits/i);
        const sMatch   = text.match(/compris entre ([\d,]+)\s*€\s*et\s*([\d,]+)\s*€/i);
        const cdiMatch = text.match(/(\d+)%\s+en\s+CDI/i);

        const offres     = extractNum(oMatch?.[1]);
        const demandeurs = extractNum(dMatch?.[1]);
        const salary     = sMatch   ? `${sMatch[1].trim()} – ${sMatch[2].trim()} €` : 'N/A';
        const cdi        = cdiMatch ? `${cdiMatch[1]}%` : 'N/A';

        return { ...rome, offres, demandeurs, salary, cdi };
    } catch {
        return { ...rome, offres: 0, demandeurs: 0, salary: 'N/A', cdi: 'N/A' };
    }
}

async function run() {
    const browser = await puppeteer.launch({
        executablePath: CHROME,
        headless: 'new',
        args: ['--no-sandbox']
    });
    const page = await browser.newPage();
    const results = {};

    for (const dept of depts) {
        process.stdout.write(`\n▶ ${dept.name} ...`);
        const rows = [];
        for (const rome of romes) {
            process.stdout.write(` ${rome.code}`);
            const r = await scrapeRome(page, dept, rome);
            if (r.offres > 0 || r.demandeurs > 0) rows.push(r);
            await delay(300);
        }
        rows.sort((a, b) => b.offres - a.offres);
        results[dept.name] = rows;
    }

    await browser.close();

    // Print table
    console.log('\n\n═══════════════════════════════════════════════════════════');
    console.log('RÉSULTATS — Offres vs Demandeurs (ratio = concurrence)');
    console.log('═══════════════════════════════════════════════════════════');
    for (const [city, rows] of Object.entries(results)) {
        console.log(`\n📍 ${city}`);
        console.log(`${'Métier'.padEnd(35)} ${'Offres'.padStart(7)} ${'Demand.'.padStart(8)} ${'Ratio'.padStart(6)} ${'CDI'.padStart(5)}`);
        console.log('─'.repeat(70));
        for (const r of rows) {
            const ratio = r.offres > 0 ? (r.demandeurs / r.offres).toFixed(1) : '∞';
            const flag  = parseFloat(ratio) >= 3 ? ' ⚠️' : parseFloat(ratio) <= 1 ? ' ✅' : '';
            console.log(`${r.name.padEnd(35)} ${String(r.offres).padStart(7)} ${String(r.demandeurs).padStart(8)} ${ratio.padStart(6)}${flag}  ${r.cdi.padStart(5)}`);
        }
    }

    // Save raw JSON
    const out = '/Users/su6i/@-github/CV/docs/job_stats_raw.json';
    fs.writeFileSync(out, JSON.stringify(results, null, 2));
    console.log(`\n✅ Raw data saved → ${out}`);
}

run().catch(console.error);
