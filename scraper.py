#!/usr/bin/env python3
"""
Basketbalový novinky monitor
=============================
Prochazi weby ceskych basketbalovych klubu, hleda nove clanky a posila
upozorneni na Telegram.

Stav (jake clanky uz byly odeslany) se uklada do seen.json, ktery se
po kazdem behu commitne zpet do repozitare (viz .github/workflows/scrape.yml).
"""

import json
import os
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

STATE_FILE = "seen.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


# ---------------------------------------------------------------------------
# Konfigurace webu
# ---------------------------------------------------------------------------
# Kazdy web ma:
#   name       - jak se bude jmenovat v notifikaci
#   list_url   - stranka, kde se vypisuji novinky/clanky
#   base_url   - pro slozeni relativnich odkazu na absolutni
#   pattern    - regex, ktery pozna odkaz na clanek (aplikuje se na href)
#   exclude    - (volitelne) seznam slugu/kousku url, ktere se maji vyradit
#                (pouziva se hlavne u webu, kde clanky nemaji vlastni
#                predponu v URL - viz BK Usti, BK Opava)
#   min_hyphens- (volitelne) minimalni pocet pomlcek ve slugu, aby se
#                odkaz povazoval za clanek (pomaha odfiltrovat menu)

SITES = [
    {
        "name": "ERA Basketball Nymburk",
        "list_url": "https://www.nymburk.basketball/archiv.asp",
        "base_url": "https://www.nymburk.basketball",
        "pattern": r"/clanek\.asp\?[^\"']*id=[\w\-]+",
    },
    {
        "name": "BK GAPA Hradec Kralove",
        "list_url": "https://bkhk.cz/archive",
        "base_url": "https://bkhk.cz",
        "pattern": r"/article/\d+-[\w\-]+",
    },
    {
        "name": "Srsni Photomate Pisek",
        "list_url": "https://www.srsni.com/archive",
        "base_url": "https://www.srsni.com",
        "pattern": r"/article/\d+-[\w\-]+",
    },
    {
        "name": "NH Ostrava",
        "list_url": "https://nhbasket.cz/clanky/",
        "base_url": "https://nhbasket.cz",
        "pattern": r"/clanek/[\w\-]+/?",
    },
    {
        "name": "SK Slavia Praha ERA NBK",
        "list_url": "https://www.slavia.basketball/",
        "base_url": "https://www.slavia.basketball",
        "pattern": r"/aktuality/[\w\-]+",
    },
    {
        "name": "SLUNETA Usti nad Labem",
        "list_url": "https://www.bkusti.cz/rub-archiv",
        "base_url": "https://www.bkusti.cz",
        "pattern": r"^/[\w\-]+/?$",
        "exclude_prefixes": ["rub-", "tymy-", "kontakt", "prispevky", "haly_"],
        "min_hyphens": 3,
    },
    {
        "name": "USK Praha",
        "list_url": "https://www.uskpraha.cz/clanky",
        "base_url": "https://www.uskpraha.cz",
        "pattern": r"/c/[\w\-]+-\d+",
    },
    {
        "name": "BK Olomoucko",
        "list_url": "http://www.bkredstone.cz/blog/list/",
        "base_url": "http://www.bkredstone.cz",
        "pattern": r"/blog/detail/\d+",
    },
    {
        "name": "BK Pardubice",
        "list_url": "https://bkpardubice.cz/novinky",
        "base_url": "https://bkpardubice.cz",
        "pattern": r"/novinka-[\w\-]+",
    },
    {
        "name": "BK Opava",
        "list_url": "https://www.bkopava.cz/novinky",
        "base_url": "https://www.bkopava.cz",
        "pattern": r"^/[\w\-]+/?$",
        "exclude_prefixes": [
            "vstupne", "zapasy", "a-tym", "mladez-tymy", "o-klubu",
            "partneri", "spolupracujeme", "podporujeme", "vstupenky",
            "permanentky", "opavska-6", "sportovni-centrum-mladeze",
            "sportovni-stredisko-mladeze", "basketbalove-pripravky-na-zs",
            "uspechy", "historie", "viceucelova-hala-opava", "ke-stazeni",
            "kontakty", "divosky-opava", "tv-sgo", "fpf-su-v-opave",
            "charita-opava", "matyas-tazbirek", "jeziskova-vnoucata",
            "business-club", "novinky",
        ],
        "min_hyphens": 3,
    },
    {
        "name": "PUMPA Basket Brno",
        "list_url": "https://www.basketbrno.cz/clanky",
        "base_url": "https://www.basketbrno.cz",
        "pattern": r"/c/[\w\-]+-\d+",
    },
    {
        "name": "BK ARMEX ENERGY Decin",
        "list_url": "https://www.bkdecin.cz/aktuality/",
        "base_url": "https://www.bkdecin.cz",
        "pattern": r"/aktuality/[\w\-]+-\d+/?",
    },
    {
        "name": "BK Lokomotiva Plzen",
        "list_url": "https://www.bkloko-plzen.cz/o-nas/aktuality/",
        "base_url": "https://www.bkloko-plzen.cz",
        "pattern": r"/news/\d+/\d+/[\w\-]+/?",
    },
]


# ---------------------------------------------------------------------------
# Pomocne funkce
# ---------------------------------------------------------------------------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram token/chat_id neni nastaveny, notifikaci vypisuji jen do logu:")
        print(text)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=20,
    )
    if not resp.ok:
        print(f"Chyba pri odesilani na Telegram: {resp.status_code} {resp.text}")


def slug_excluded(path, site):
    prefixes = site.get("exclude_prefixes", [])
    slug = path.strip("/")
    for p in prefixes:
        if slug.startswith(p):
            return True
    min_hyphens = site.get("min_hyphens")
    if min_hyphens and slug.count("-") < min_hyphens:
        return True
    return False


def extract_articles(html, site):
    """Vrati list (url, title) dvojic nalezenych na strance."""
    from urllib.parse import urlparse

    soup = BeautifulSoup(html, "html.parser")
    pattern = re.compile(site["pattern"])
    is_flat_slug_site = site["pattern"].startswith("^/")
    found = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]

        if is_flat_slug_site:
            # u webu s "flat" slugy (bkusti, bkopava) kontrolujeme jen cestu bez domeny
            path = urlparse(href).path if href.startswith("http") else href
            if not pattern.match(path):
                continue
            if slug_excluded(path, site):
                continue
        else:
            if pattern.search(href) is None:
                continue

        full_url = urljoin(site["base_url"], href)
        title = a.get_text(strip=True)
        if not title:
            continue
        # u nekterych webu jsou v odkazu i datum/kategorie slepene s titulkem,
        # necháváme tak jak je - lepsi mit surovy text nez nic
        if full_url not in found or len(title) > len(found[full_url]):
            found[full_url] = title
    return list(found.items())


def check_site(site, state):
    name = site["name"]
    seen_urls = set(state.get(name, []))
    is_first_run = len(seen_urls) == 0

    try:
        resp = requests.get(site["list_url"], headers=HEADERS, timeout=25)
        resp.raise_for_status()
    except Exception as e:
        print(f"[{name}] chyba pri stahovani: {e}")
        return seen_urls, []

    articles = extract_articles(resp.text, site)
    if not articles:
        print(f"[{name}] nenalezen zadny clanek - zkontroluj selektor/pattern v scraper.py")
        return seen_urls, []

    new_items = []
    current_urls = set()
    for url, title in articles:
        current_urls.add(url)
        if url not in seen_urls:
            new_items.append((url, title))

    updated_seen = seen_urls | current_urls

    if is_first_run:
        # Pri prvnim behu si jen zapamatujeme aktualni clanky, neposilame
        # notifikace za vsechny (jinak by prisel spam pri prvnim spusteni).
        print(f"[{name}] prvni beh - ukladam {len(current_urls)} clanku jako zakladni stav, bez notifikaci")
        return updated_seen, []

    return updated_seen, new_items


def main():
    state = load_state()
    total_new = 0

    for site in SITES:
        updated_seen, new_items = check_site(site, state)
        state[site["name"]] = sorted(updated_seen)

        for url, title in new_items:
            total_new += 1
            message = f"🏀 <b>{site['name']}</b>\n{title}\n{url}"
            send_telegram(message)
            print(f"[{site['name']}] NOVY CLANEK: {title} -> {url}")
            time.sleep(1)  # sance na Telegram rate limit

    save_state(state)
    print(f"Hotovo. Novych clanku celkem: {total_new}")


if __name__ == "__main__":
    main()
