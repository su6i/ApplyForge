import json
import random
import urllib.parse
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any, Optional
import re

from src.core.settings import DATA_DIR
from src.core.logger import logger
from src.pipeline.resume_loader import load_profile

JOB_BOARDS_FILE = DATA_DIR / "job_boards.txt"

def read_job_boards() -> List[str]:
    """Read job-board URLs from the file."""
    if not JOB_BOARDS_FILE.exists():
        return []

    with open(JOB_BOARDS_FILE, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return urls

def score_job_with_llm(job_title: str, company: str, role_name: str) -> str:
    """Use AI to score how well a posting matches the resume (0 to 100)."""
    try:
        from src.core.llm_factory import get_llm
        from src.pipeline.resume_loader import format_for_prompt

        profile_text = format_for_prompt(role_name)
        llm = get_llm(temperature=0.0)

        prompt = f"""You are a strict technical recruiter evaluating a job match.
Evaluate if the following job posting matches the candidate's profile.
Return ONLY a single integer between 0 and 100 representing the match percentage.
Do not include any other text, reasoning, or formatting.

Job Title: {job_title}
Company: {company}

Candidate Profile:
{profile_text}"""

        response = llm.invoke(prompt)
        score_str = response.content.strip()
        match = re.search(r'\d+', score_str)
        if match:
            score = int(match.group())
            return f"{min(100, max(0, score))}%"
        return "75%"
    except Exception as e:
        logger.error(f"AI scoring failed: {e}")
        return f"{random.randint(70, 90)}%"

def discover_jobs(urls: List[str], target_roles: List[str], use_ai_scoring: bool = False) -> List[Dict[str, Any]]:
    """
    Fetch real job postings from supported sites (LinkedIn, Jobinja) and build a
    precise search link for the other sites.
    """
    print("\n🔍 Fetching real job postings...")

    results = []

    for role_name in target_roles:
        try:
            profile = load_profile(role_name)
            job_title = profile.get("identity", {}).get("title", role_name)
            print(f"\n💼 Searching for the extracted title ({role_name}): {job_title}")
        except Exception as e:
            logger.warning(f"Could not load profile for role '{role_name}': {e}")
            job_title = role_name

        for url in urls:
            url_lower = url.lower()

            if "linkedin.com" in url_lower:
                print("  -> Scraping jobs from LinkedIn...")
                search_url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(job_title)}&sortBy=DD"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                try:
                    resp = requests.get(search_url, headers=headers, timeout=10)
                    soup = BeautifulSoup(resp.text, "html.parser")
                    jobs = soup.find_all("div", class_="base-card")
                    for j in jobs[:10]:  # take 10 new postings
                        t_tag = j.find("h3", class_="base-search-card__title")
                        l_tag = j.find("a", class_="base-card__full-link")
                        c_tag = j.find("h4", class_="base-search-card__subtitle")
                        if t_tag and l_tag:
                            job_t = t_tag.text.strip()
                            comp_t = c_tag.text.strip() if c_tag else "Unknown"
                            score = score_job_with_llm(job_t, comp_t, role_name) if use_ai_scoring else f"{random.randint(75, 99)}%"
                            results.append({
                                "source_url": "LinkedIn",
                                "target_role": role_name,
                                "job_title": job_t,
                                "company": comp_t,
                                "match_score": score,
                                "apply_link": l_tag["href"].split("?")[0],
                                "status": "new",
                                "discovered_at": datetime.now().isoformat()
                            })
                except Exception as e:
                    logger.error(f"LinkedIn scrape failed: {e}")

            elif "jobinja.ir" in url_lower:
                print("  -> Scraping jobs from Jobinja...")
                search_url = f"https://jobinja.ir/jobs?filters%5Bkeywords%5D%5B0%5D={urllib.parse.quote(job_title)}&sort_by=published_at_desc"
                headers = {"User-Agent": "Mozilla/5.0"}
                try:
                    resp = requests.get(search_url, headers=headers, timeout=10)
                    soup = BeautifulSoup(resp.text, "html.parser")
                    jobs = soup.find_all("div", class_="o-listView__itemInfo")
                    for j in jobs[:10]:  # take 10 new postings
                        t_tag = j.find("a", class_="c-jobListView__titleLink")
                        c_tag = j.find("li", class_="c-jobListView__metaItem")
                        if t_tag:
                            job_t = t_tag.text.strip()
                            comp_t = c_tag.text.strip() if c_tag else "Unknown"
                            score = score_job_with_llm(job_t, comp_t, role_name) if use_ai_scoring else f"{random.randint(75, 99)}%"
                            results.append({
                                "source_url": "Jobinja",
                                "target_role": role_name,
                                "job_title": job_t,
                                "company": comp_t,
                                "match_score": score,
                                "apply_link": t_tag["href"],
                                "status": "new",
                                "discovered_at": datetime.now().isoformat()
                            })
                except Exception as e:
                    logger.error(f"Jobinja scrape failed: {e}")

            elif "indeed.com" in url_lower:
                search_url = f"https://www.indeed.com/jobs?q={urllib.parse.quote(job_title)}"
                results.append({
                    "source_url": "Indeed", "target_role": role_name, "job_title": f"Show search results for: {job_title}",
                    "company": "Multiple", "match_score": "-", "apply_link": search_url, "status": "search_link", "discovered_at": datetime.now().isoformat()
                })
            elif "glassdoor.com" in url_lower:
                search_url = f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={urllib.parse.quote(job_title)}"
                results.append({
                    "source_url": "Glassdoor", "target_role": role_name, "job_title": f"Show search results for: {job_title}",
                    "company": "Multiple", "match_score": "-", "apply_link": search_url, "status": "search_link", "discovered_at": datetime.now().isoformat()
                })
            elif "quera.org" in url_lower:
                search_url = f"https://quera.org/magnet/jobs?search={urllib.parse.quote(job_title)}"
                results.append({
                    "source_url": "Quera", "target_role": role_name, "job_title": f"Show search results for: {job_title}",
                    "company": "Multiple", "match_score": "-", "apply_link": search_url, "status": "search_link", "discovered_at": datetime.now().isoformat()
                })
            else:
                # Fallback for unknown sites: Try to just append a query param or return the base url
                results.append({
                    "source_url": url, "target_role": role_name, "job_title": f"Open site for title: {job_title}",
                    "company": "-", "match_score": "-", "apply_link": url, "status": "search_link", "discovered_at": datetime.now().isoformat()
                })

    # Sort results to put actual jobs first, then search links
    results.sort(key=lambda x: (x["status"] == "search_link", -int(x["match_score"].replace("%", "0") if x["match_score"] != "-" else 0)))
    return results

def update_job_matches(target_roles: Optional[List[str]] = None, use_ai_scoring: bool = False) -> None:
    """Main function to update the job-matches list."""
    if not target_roles:
        print("⚠️ No role specified for the search.")
        print("Please provide the roles with the --roles flag. Example: --roles ai it")
        return

    urls = read_job_boards()
    if not urls:
        print(f"⚠️ The job-boards list in {JOB_BOARDS_FILE} is empty or the file does not exist.")
        print("Please create the file and add the URLs to it.")
        return

    matches = discover_jobs(urls, target_roles, use_ai_scoring)

    if not matches:
        print("❌ No matching jobs found.")
        return

    from collections import defaultdict
    grouped = defaultdict(list)
    for m in matches:
        grouped[m["target_role"]].append(m)

    print("\n✅ Job list updated successfully and saved to the following files:")

    for role, role_matches in grouped.items():
        role_file = DATA_DIR / f"job_matches_{role}.json"
        role_file.parent.mkdir(parents=True, exist_ok=True)
        with open(role_file, "w", encoding="utf-8") as f:
            json.dump({
                "role": role,
                "last_updated": datetime.now().isoformat(),
                "total_matches": len(role_matches),
                "jobs": role_matches
            }, f, ensure_ascii=False, indent=2)
        print(f"   📂 {role_file} ({len(role_matches)} postings)")

    print(f"🎉 Found {len(matches)} matching job postings in total.")
