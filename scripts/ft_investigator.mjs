import puppeteer from 'puppeteer';
import fs from 'fs';

(async () => {
    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();
    
    console.log("Navigating to IT Sector Page for Department 34 (Montpellier)...");
    await page.goto('https://dataemploi.francetravail.fr/emploi/secteur/chiffres-cles/DEP/34/96', { waitUntil: 'networkidle0', timeout: 30000 });
    
    await new Promise(r => setTimeout(r, 2000));
    
    const text = await page.evaluate(() => document.body.innerText);
    fs.writeFileSync('/tmp/secteur_34.txt', text);
    
    const html = await page.evaluate(() => document.body.innerHTML);
    fs.writeFileSync('/tmp/secteur_34.html', html);
    
    console.log("Saved text to /tmp/secteur_34.txt");
    await browser.close();
})();
