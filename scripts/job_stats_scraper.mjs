import puppeteer from 'puppeteer';
import fs from 'fs';

// List of main IT ROME Codes (M18xx)
const romes = [
    { code: 'M1801', name: 'Administration de systèmes d\'information' },
    { code: 'M1802', name: 'Expertise et support en SI' },
    { code: 'M1803', name: 'Direction des systèmes d\'information' },
    { code: 'M1804', name: 'Études et dev. de réseaux de télécoms' },
    { code: 'M1805', name: 'Études et développement informatique' },
    { code: 'M1806', name: 'Conseil et maîtrise d\'ouvrage en SI' },
    { code: 'M1810', name: 'Production et exploitation de SI' },
    { code: 'M1827', name: 'Ingénieur / Ingénieure DevOps' },
    { code: 'M1821', name: 'Data Scientist / Analyst' },
    { code: 'M1826', name: 'Expert Cyber-sécurité' }
];

const depts = [
    { code: 'FR', name: 'کل کشور (National)', type: 'NAT' },
    { code: '75', name: 'Paris (75)', type: 'DEP' },
    { code: '69', name: 'Lyon (69)', type: 'DEP' },
    { code: '13', name: 'Marseille (13)', type: 'DEP' },
    { code: '31', name: 'Toulouse (31)', type: 'DEP' },
    { code: '06', name: 'Nice (06)', type: 'DEP' },
    { code: '44', name: 'Nantes (44)', type: 'DEP' },
    { code: '34', name: 'Montpellier (34)', type: 'DEP' },
    { code: '67', name: 'Strasbourg (67)', type: 'DEP' },
    { code: '33', name: 'Bordeaux (33)', type: 'DEP' },
    { code: '59', name: 'Lille (59)', type: 'DEP' },
    { code: '35', name: 'Rennes (35)', type: 'DEP' },
    { code: '51', name: 'Reims (51)', type: 'DEP' },
    { code: '83', name: 'Toulon (83)', type: 'DEP' },
    { code: '42', name: 'Saint-Étienne (42)', type: 'DEP' },
    { code: '38', name: 'Grenoble (38)', type: 'DEP' }
];

// Helper to wait
const delay = ms => new Promise(res => setTimeout(res, ms));

async function run() {
    console.log("Starting browser to gather data...");
    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();
    
    const finalData = {};

    for (let dept of depts) {
        console.log(`\nFetching data for ${dept.name}...`);
        let cityResults = [];
        
        for (let rome of romes) {
            const url = `https://dataemploi.francetravail.fr/emploi/metier/chiffres-cles/${dept.type}/${dept.code}/${rome.code}`;
            let demandeurs = 0;
            let offres = 0;
            let salary = 'N/A';
            let cdi = 'N/A';
            
            try {
                await page.goto(url, { waitUntil: 'networkidle0', timeout: 10000 });
                
                try {
                    // Try to extract directly from text based on known patterns
                    const text = await page.evaluate(() => document.body.innerText);
                    
                    const dMatch = text.match(/Demandeurs d'emploi[\s\n]*([\d,]+)[\s\n]*inscrits/i);
                    const oMatch = text.match(/Offres d'emploi[\s\n]*([\d,]+)[\s\n]*diffusées/i);
                    const sMatch = text.match(/compris entre\s*([\d,\s]+)€\s*et\s*([\d,\s]+)€/i);
                    const cdiMatch = text.match(/CDI\s*\(\s*(\d+)%\s*\)/i);
                    
                    if (dMatch) demandeurs = parseInt(dMatch[1].replace(/,/g, ''), 10) || 0;
                    if (oMatch) offres = parseInt(oMatch[1].replace(/,/g, ''), 10) || 0;
                    if (sMatch) salary = `${sMatch[1].trim()} - ${sMatch[2].trim()} €`;
                    if (cdiMatch) cdi = `${cdiMatch[1]}%`;
                } catch (e) {
                    console.log(`Error parsing ${rome.name}: ${e.message}`);
                }
            } catch (err) {
                // Ignore timeout
            }
            
            if (offres > 0 || demandeurs > 0) {
                cityResults.push({
                    name: rome.name,
                    code: rome.code,
                    offres: offres,
                    demandeurs: demandeurs,
                    salary: salary,
                    cdi: cdi
                });
            }
        }
        
        // Sort by offres descending and take top 5
        cityResults.sort((a, b) => b.offres - a.offres);
        const top5 = cityResults.slice(0, 5);
        finalData[dept.name] = top5;
        
        console.log(`Top 5 for ${dept.name}:`);
        top5.forEach(t => console.log(`  - ${t.name} (${t.code}): ${t.offres} offres, ${t.demandeurs} demandeurs, Salary: ${t.salary}, CDI: ${t.cdi}`));
    }
    
    await browser.close();
    
    // Generate Markdown
    console.log("\nGenerating Markdown file...");
    let md = `# آمار بازار کار IT در کل کشور و ۱۵ شهر بزرگ فرانسه\n\n`;
    md += `این فایل ۵ گرایش پر تقاضا (بیشترین آگهی شغلی) را در سطح کشوری و همچنین به تفکیک هر یک از ۱۵ شهر بزرگ فرانسه بر اساس آخرین داده‌های France Travail نشان می‌دهد.\n\n`;
    
    for (let dept of depts) {
        if (dept.type === 'NAT') {
            md += `## 🌍 آمار کل کشور (National)\n`;
        } else {
            md += `### ${dept.name}\n`;
        }
        
        md += `| رتبه | گرایش شغلی (کد ROME) | پیشنهادهای کاری | متقاضیان کار | رنج حقوق (۸۰٪) | سهم CDI |\n`;
        md += `|:---:|:---|:---:|:---:|:---:|:---:|\n`;
        
        const top5 = finalData[dept.name] || [];
        if (top5.length === 0) {
            md += `| - | داده‌ای یافت نشد | - | - | - | - |\n`;
        } else {
            top5.forEach((item, index) => {
                md += `| ${index + 1} | **${item.name}** (${item.code}) | ${item.offres.toLocaleString('fa-IR')} | ${item.demandeurs.toLocaleString('fa-IR')} | ${item.salary} | ${item.cdi} |\n`;
            });
        }
        md += `\n`;
    }
    md += `\n---\n<sub>*By [Su6iant](https://linkedin.com/in/su6i)*</sub>\n`;
    
    const mdPath = '/Users/su6i/@-github/CV/docs/IT_Job_Market_Stats.fa.md';
    fs.writeFileSync(mdPath, md);
    console.log(`Markdown saved to ${mdPath}`);
}


run().catch(err => console.error(err));
