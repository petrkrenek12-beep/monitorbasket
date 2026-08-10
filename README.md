# Basket novinky monitor

Hlídá 13 webů českých basketbalových klubů a při novém článku pošle
zprávu do Telegramu. Běží na GitHub Actions (zdarma), takže funguje
i když máš vypnutý počítač i mobil.

Sledované kluby: Nymburk, BK GAPA Hradec Králové, Sršni Písek, NH Ostrava,
SK Slavia Praha, SLUNETA Ústí nad Labem, USK Praha, BK Olomoucko,
BK Pardubice, BK Opava, Basket Brno, BK Děčín, BK Lokomotiva Plzeň.

## 1. Založ si Telegram bota (5 minut)

1. V Telegramu najdi **@BotFather** a napiš mu `/newbot`.
2. Dej botovi jméno a username (username musí končit na `bot`, např. `petr_basket_bot`).
3. BotFather ti pošle **token** – dlouhý řetězec typu `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`.
   Ten si schovej, budeš ho potřebovat jako `TELEGRAM_BOT_TOKEN`.
4. Najdi si svého bota v Telegramu (podle username) a napiš mu cokoliv,
   třeba "ahoj" – aby s tebou mohl začít komunikovat.
5. Zjisti své **chat_id**: otevři v prohlížeči (nahraď TOKEN svým tokenem):
   `https://api.telegram.org/botTOKEN/getUpdates`
   V odpovědi najdeš `"chat":{"id":123456789, ...}` – to číslo je tvoje
   `TELEGRAM_CHAT_ID`.

## 2. Založ GitHub repozitář

1. Na [github.com](https://github.com) klikni na **New repository**,
   pojmenuj ho třeba `basket-monitor`, klidně jako **Private**.
2. Nahraj do něj všechny soubory z této složky (přes web rozhraní
   "Add file → Upload files", nebo přes git):
   ```
   git init
   git add .
   git commit -m "Basket monitor"
   git branch -M main
   git remote add origin https://github.com/TVOJE-JMENO/basket-monitor.git
   git push -u origin main
   ```

## 3. Nastav secrets (token a chat_id)

V repozitáři: **Settings → Secrets and variables → Actions → New repository secret**

- `TELEGRAM_BOT_TOKEN` = token z BotFather
- `TELEGRAM_CHAT_ID` = tvoje chat_id

## 4. Spusť poprvé

V repozitáři: záložka **Actions → Basket novinky monitor → Run workflow**.

**Důležité:** první běh si jen zapamatuje aktuální články na všech webech
jako výchozí stav – nepošle ti tedy 50 zpráv najednou. Notifikace přijdou
až na články, které vyjdou **po** prvním spuštění.

Poté už workflow běží automaticky každých 15 minut (soubor
`.github/workflows/scrape.yml`, dá se změnit v `cron`).

## Jak to funguje

- `scraper.py` stáhne stránku s novinkami/aktualitami z každého webu,
  najde odkazy na články podle vzorku URL (regex) a porovná je se
  seznamem už viděných článků v `seen.json`.
- Nové články se pošlou na Telegram a `seen.json` se uloží zpět do
  repozitáře, aby si stav pamatoval i příští běh.
- Weby jsou různé CMS platformy, takže každý web má v `scraper.py`
  v seznamu `SITES` vlastní konfiguraci (`list_url` = stránka s výpisem
  novinek, `pattern` = jak vypadá URL článku).

## Co může být potřeba doladit

Dva weby (**SLUNETA Ústí nad Labem** a **BK Opava**) nemají v URL
článků žádnou pěknou předponu (`/nazev-clanku` rovnou v kořeni webu),
takže scraper je pozná heuristikou (vylučuje známé odkazy v menu,
vyžaduje aspoň 3 pomlčky ve slugu). Pokud by po pár dnech provozu
chodily false-positive notifikace (např. na nějakou podstránku) nebo
naopak chyběl nějaký článek, stačí mi dát vědět nebo upravit
`exclude_prefixes` / `min_hyphens` u daného webu v `scraper.py`.

**BK Děčín** a **BK Lokomotiva Plzeň** mají v robots.txt zákaz pro
automatizovaný přístup některým nástrojům – běžný `requests` s
prohlížečovou hlavičkou (což skript používá) by měl fungovat bez
problémů, ale kdyby ne, dej vědět.

## Lokální test (nepovinné)

```
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
python scraper.py
```

Bez nastavených proměnných skript notifikace jen vypíše do konzole
místo posílání na Telegram – hodí se to na ověření, že parsování webů
funguje.

## Změna intervalu

V `.github/workflows/scrape.yml` uprav řádek s `cron`. Např. každou
hodinu: `"0 * * * *"`. GitHub Actions cron může mít v době většího
zatížení zpoždění v řádu minut, to je normální.
