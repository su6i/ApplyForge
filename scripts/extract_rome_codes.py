import urllib.request
import re
import json

def run():
    url = "https://candidat.francetravail.fr/metierscope/secteurs-activite/96/informatique-et-telecommunication"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    print(f"Fetching URL: {url}...")
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            
        print("Page fetched successfully. Extracting ROME codes...")
        
        # Regex to find links: href="/metierscope/fiche-metier/M1805/etudes-et-developpement-informatique"
        # and the text inside the anchor.
        # Example pattern: <a class="card-metier-link" href="/metierscope/fiche-metier/([A-Z]\d{4})/[^"]*">.*?<span class="card-metier-title">(.*?)</span>
        # Let's use a very broad regex to catch all /fiche-metier/ links and their surrounding text.
        
        matches = re.findall(r'href="[^"]*?/fiche-metier/([A-Z]\d{4})/([^"]*?)"', html, re.IGNORECASE)
        
        results = []
        seen = set()
        
        # In case we can't find direct matches because of dynamic HTML class names,
        # we can also look for raw links and clean up their slugs as names.
        for code, slug in matches:
            if code not in seen:
                seen.add(code)
                # Convert slug to a nicer title: e.g. "etudes-et-developpement-informatique" -> "Etudes et developpement informatique"
                nice_name = slug.replace('-', ' ').strip().capitalize()
                
                results.append({
                    "code": code,
                    "name": nice_name,
                    "slug": slug
                })
        
        # If matches list is empty, let's print some HTML snippet to diagnose, or search for a looser regex.
        if not results:
            print("No simple matches found via regex. Trying fallback regex...")
            # Fallback regex for any fiche-metier links: /fiche-metier/M1805/something
            fallback = re.findall(r'/fiche-metier/([A-Z]\d{4})/([a-zA-Z0-9\-_]+)', html)
            for code, slug in fallback:
                if code not in seen:
                    seen.add(code)
                    nice_name = slug.replace('-', ' ').strip().capitalize()
                    results.append({
                        "code": code,
                        "name": nice_name,
                        "slug": slug
                    })
                    
        print(f"\nFound {len(results)} ROME codes:\n")
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    run()
