#!/usr/bin/env python3
"""Scrape new AI jobs and save to new_jobs.json for the Claude agent to summarize."""

import hashlib
import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
SEEN_JOBS_FILE = BASE_DIR / "seen_jobs.json"
CONFIG_FILE = BASE_DIR / "config.yaml"
NEW_JOBS_FILE = BASE_DIR / "new_jobs.json"

logging.basicConfig(
    filename=BASE_DIR / "job_digest.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

BIG_TECH = {
    "google", "meta", "apple", "microsoft", "amazon", "netflix", "uber",
    "airbnb", "salesforce", "oracle", "ibm", "intel", "nvidia", "twitter",
    "x corp", "bytedance", "tiktok", "spotify", "linkedin", "adobe",
    "palantir", "snowflake", "databricks",
}

AI_KEYWORDS = [
    "ai", "ml", "machine learning", "artificial intelligence", "llm", "nlp",
    "deep learning", "data scientist", "computer vision", "robotics",
    "generative", "foundation model", "research scientist", "mlops",
    "reinforcement learning", "language model", "large language",
]


def load_config():
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def load_seen_jobs():
    if SEEN_JOBS_FILE.exists():
        with open(SEEN_JOBS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_jobs(seen):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(list(seen), f)


def url_id(url):
    return hashlib.md5(url.encode()).hexdigest()


def is_ai_role(title):
    t = title.lower()
    return any(kw in t for kw in AI_KEYWORDS)


def is_big_tech(company):
    c = company.lower()
    return any(bt in c for bt in BIG_TECH)


def clean_text(html):
    return BeautifulSoup(html or "", "html.parser").get_text(separator=" ").strip()


# ── Scrapers ──────────────────────────────────────────────────────────────────

def scrape_rss_feeds(feed_urls):
    jobs = []
    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                jobs.append({
                    "title": entry.get("title", ""),
                    "company": entry.get("author", feed.feed.get("title", "")),
                    "url": entry.get("link", ""),
                    "description": clean_text(entry.get("summary", "")),
                    "location": "Remote",
                    "source": feed.feed.get("title", feed_url),
                })
            log.info(f"RSS {feed_url}: {len(feed.entries)} entries")
        except Exception as e:
            log.error(f"RSS {feed_url} failed: {e}")
    return jobs


def scrape_linkedin(query, location):
    jobs = []
    try:
        url = (
            "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={requests.utils.quote(query)}"
            f"&location={requests.utils.quote(location)}"
            "&f_TPR=r86400"
            "&start=0"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select("li"):
            title_el = card.select_one(".base-search-card__title")
            company_el = card.select_one(".base-search-card__subtitle")
            location_el = card.select_one(".job-search-card__location")
            link_el = card.select_one("a.base-card__full-link")
            if not title_el or not link_el:
                continue
            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "",
                "url": link_el["href"].split("?")[0],
                "description": "",
                "location": location_el.get_text(strip=True) if location_el else location,
                "source": "LinkedIn",
            })
        log.info(f"LinkedIn '{query}' / '{location}': {len(jobs)} jobs")
        time.sleep(2)
    except Exception as e:
        log.error(f"LinkedIn scrape failed ({query}): {e}")
    return jobs


def scrape_indeed(query, location):
    jobs = []
    try:
        url = (
            "https://www.indeed.com/jobs"
            f"?q={requests.utils.quote(query)}"
            f"&l={requests.utils.quote(location)}"
            "&fromage=1&sort=date"
        )
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        for card in soup.select('[data-testid="slider_item"]'):
            title_el = card.select_one('[data-testid="jobTitle"]')
            company_el = card.select_one('[data-testid="company-name"]')
            location_el = card.select_one('[data-testid="text-location"]')
            link_el = card.select_one("a[id^='job_']")
            if not title_el or not link_el:
                continue
            href = link_el.get("href", "")
            if not href.startswith("http"):
                href = "https://www.indeed.com" + href
            jobs.append({
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "",
                "url": href,
                "description": "",
                "location": location_el.get_text(strip=True) if location_el else location,
                "source": "Indeed",
            })
        log.info(f"Indeed '{query}' / '{location}': {len(jobs)} jobs")
        time.sleep(2)
    except Exception as e:
        log.error(f"Indeed scrape failed ({query}): {e}")
    return jobs


def scrape_custom_urls(urls):
    jobs = []
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.text, "html.parser")
            for a in soup.select("a[href]"):
                text = a.get_text(strip=True)
                href = a["href"]
                if len(text) < 10:
                    continue
                if not href.startswith("http"):
                    href = requests.compat.urljoin(url, href)
                jobs.append({
                    "title": text,
                    "company": "",
                    "url": href,
                    "description": "",
                    "location": "",
                    "source": url,
                })
        except Exception as e:
            log.error(f"Custom URL {url} failed: {e}")
    return jobs


# ── Filter + deduplicate ──────────────────────────────────────────────────────

def filter_new_jobs(jobs, seen):
    seen_urls = set()
    result = []
    for job in jobs:
        if not job["url"]:
            continue
        jid = url_id(job["url"])
        if jid in seen or job["url"] in seen_urls:
            continue
        if not is_ai_role(job["title"]):
            continue
        if is_big_tech(job["company"]):
            continue
        seen_urls.add(job["url"])
        job["id"] = jid
        result.append(job)
    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("── Scrape run starting ──")
    cfg = load_config()
    seen = load_seen_jobs()

    all_jobs = []
    all_jobs += scrape_rss_feeds(cfg.get("rss_feeds", []))

    for term in cfg.get("search_terms", ["AI engineer"]):
        for loc in cfg.get("locations", ["San Francisco, CA"]):
            if loc.lower() == "remote":
                continue
            all_jobs += scrape_linkedin(term, loc)
            all_jobs += scrape_indeed(term, loc)

    all_jobs += scrape_custom_urls(cfg.get("custom_urls", []))
    log.info(f"Total collected: {len(all_jobs)}")

    new_jobs = filter_new_jobs(all_jobs, seen)
    log.info(f"New AI jobs after filtering: {len(new_jobs)}")

    # Save new jobs for the Claude agent to summarize
    with open(NEW_JOBS_FILE, "w") as f:
        json.dump(new_jobs, f, indent=2)

    # Mark everything seen so they don't reappear tomorrow
    for job in all_jobs:
        if job.get("url"):
            seen.add(url_id(job["url"]))
    save_seen_jobs(seen)

    print(f"Saved {len(new_jobs)} new jobs to {NEW_JOBS_FILE}")
    log.info(f"── Scrape done: {len(new_jobs)} new jobs ──")

    # Push to GitHub so the remote Claude agent can pick it up
    _git_push()


def _git_push():
    cmds = [
        ["git", "add", "new_jobs.json", "seen_jobs.json"],
        ["git", "commit", "--allow-empty", "-m", f"scrape: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        ["git", "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
        if result.returncode != 0:
            log.error(f"git command failed: {' '.join(cmd)}\n{result.stderr}")
            print(f"Warning: {' '.join(cmd)} failed — {result.stderr.strip()}")
        else:
            log.info(f"git: {' '.join(cmd)}")


if __name__ == "__main__":
    main()
