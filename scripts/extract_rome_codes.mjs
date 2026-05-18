import puppeteer from 'puppeteer';

async function run() {
    const url = 'https://candidat.francetravail.fr/metierscope/secteurs-activite/96/informatique-et-telecommunication';
    console.log(`Navigating to ${url}...`);

    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();
    
    try {
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
        
        // Wait for links to appear
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
                    // Clean text (sometimes contains arrow characters or newlines)
                    const cleanText = text.replace(/[\n\r→]/g, '').trim();
                    
                    // Prevent duplicates
                    if (!items.find(i => i.code === code)) {
                        items.push({ code, name: cleanText, url: 'https://candidat.francetravail.fr' + href });
                    }
                }
            });
            return items;
        });

        console.log(`\nFound ${results.length} unique IT/Telecom jobs:\n`);
        console.log(JSON.stringify(results, null, 2));

    } catch (err) {
        console.error('Error during scraping:', err);
    } finally {
        await browser.close();
    }
}

run();
