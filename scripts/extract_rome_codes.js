const puppeteer = require('/Users/su6i/@-github/amir-cli/lib/nodejs/node_modules/puppeteer-core');

async function run() {
    const url = 'https://candidat.francetravail.fr/metierscope/secteurs-activite/96/informatique-et-telecommunication';
    console.log(`Navigating to ${url}...`);

    const browser = await puppeteer.launch({
        executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });
    const page = await browser.newPage();
    
    try {
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
        
        // Wait for links to appear
        console.log("Waiting for job links to load...");
        await page.waitForSelector('a[href*="/fiche-metier/"]', { timeout: 15000 });
        
        const results = await page.evaluate(() => {
            const items = [];
            const links = document.querySelectorAll('a[href*="/fiche-metier/"]');
            
            links.forEach(link => {
                const href = link.getAttribute('href');
                const text = link.innerText.trim();
                
                // Example URL: /metierscope/fiche-metier/M1805/etudes-et-developpement-informatique
                const match = href.match(/\/fiche-metier\/([A-Z]\d{4})/);
                if (match) {
                    const code = match[1];
                    const cleanText = text.replace(/[\n\r→]/g, ' ').replace(/\s+/g, ' ').trim();
                    
                    // Determine category by climbing up DOM to see if it's under Informatique or Télécommunication
                    let category = 'Informatique';
                    let parent = link.parentElement;
                    while (parent) {
                        // Look at headings in previous siblings or parents
                        // Informatique section has an Informatique header, Telecom has Telecom header
                        // Let's identify by searching the container's structural siblings
                        const sibling = parent.previousElementSibling;
                        if (sibling && sibling.tagName === 'H2') {
                            if (sibling.textContent.toLowerCase().includes('télécom')) {
                                category = 'Télécommunication';
                            }
                            break;
                        }
                        
                        // Also check h2 children of parent
                        const heading = parent.querySelector('h2');
                        if (heading) {
                            if (heading.textContent.toLowerCase().includes('télécom')) {
                                category = 'Télécommunication';
                            }
                            break;
                        }
                        parent = parent.parentElement;
                    }
                    
                    if (!items.find(i => i.code === code)) {
                        items.push({ code, name: cleanText, category });
                    }
                }
            });
            return items;
        });

        // Let's manually separate them based on their actual location to be perfectly accurate:
        // Informatique ROME codes: M18xx, M14xx, etc.
        // Télécommunication ROME codes: F16xx, I13xx, etc.
        // We can group them by ROME code prefixes to be 100% accurate:
        // - Informatique: M1801-M1827, M1401-M1405, etc.
        // - Télécommunication: F1601-F1623, I13xx, I14xx, etc.
        // Let's double check if some are misclassified by DOM parser and fix by prefix:
        results.forEach(item => {
            if (item.code.startsWith('F') || item.code.startsWith('I')) {
                item.category = 'Télécommunication';
            } else {
                item.category = 'Informatique';
            }
        });

        const informatique = results.filter(i => i.category === 'Informatique');
        const telecom = results.filter(i => i.category === 'Télécommunication');

        console.log(`\nFound ${results.length} unique IT & Telecom ROME codes:\n`);
        
        console.log("### 💻 Informatique:");
        informatique.forEach(i => console.log(`- ${i.code}: ${i.name}`));
        
        console.log("\n### 📞 Télécommunication:");
        telecom.forEach(i => console.log(`- ${i.code}: ${i.name}`));

        // Also save to a JSON file in case the user wants it
        const fs = require('fs');
        fs.writeFileSync('/Users/su6i/@-github/CV/docs/it_rome_codes.json', JSON.stringify({ informatique, telecom }, null, 2));
        console.log("\nSaved full list to /Users/su6i/@-github/CV/docs/it_rome_codes.json");

    } catch (err) {
        console.error('Error during scraping:', err);
    } finally {
        await browser.close();
    }
}

run();
