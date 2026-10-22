"""
Raccoglitore dell'archivio fonti.

Legge fonti.yaml, visita ogni fonte, aggiunge all'archivio le voci nuove
e aggiorna docs/data.json (l'archivio) e docs/stato.json (lo stato delle fonti).
Gira da solo su GitHub Actions; si può lanciare anche a mano:  python raccogli.py
"""

import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.robotparser
from datetime import datetime, timezone

import feedparser
import requests
import trafilatura
import yaml
from lxml import html as lhtml

QUI = os.path.dirname(os.path.abspath(__file__))
FILE_FONTI = os.environ.get("FONTI", os.path.join(QUI, "fonti.yaml"))
FILE_ARCHIVIO = os.path.join(QUI, "docs", "data.json")
FILE_STATO = os.path.join(QUI, "docs", "stato.json")
GNEWS = os.environ.get("GNEWS_BASE", "https://news.google.com/rss/search")

UA = "ArchivioFontiPersonale/1.0 (raccolta per uso giornalistico personale)"
TIMEOUT = 25
NUOVI_PER_FONTE = 25      # massimo voci nuove per fonte a ogni giro
TESTI_PER_FONTE = 10      # massimo testi completi scaricati per fonte a ogni giro
TESTO_MAX = 20000         # caratteri massimi del testo salvato
SOMMARIO_MAX = 600
ARCHIVIO_MAX = 8000       # voci massime conservate (le più vecchie escono)

sessione = requests.Session()
sessione.headers.update({"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9"})
_robots = {}


# ── utilità ────────────────────────────────────────────────────────────────

def adesso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ident(url):
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]


def pulisci(testo, limite=None):
    if not testo:
        return ""
    testo = re.sub(r"<[^>]+>", " ", testo)
    testo = html.unescape(testo)
    testo = re.sub(r"\s+", " ", testo).strip()
    if limite and len(testo) > limite:
        testo = testo[:limite].rsplit(" ", 1)[0] + "…"
    return testo


def scarica(url):
    r = sessione.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    if "charset" not in r.headers.get("Content-Type", "").lower():
        r.encoding = r.apparent_encoding or "utf-8"
    return r


def robots_ok(url):
    """Rispetta robots.txt: se un sito non vuole programmi, non ne leggo il testo."""
    p = urllib.parse.urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = sessione.get(base + "/robots.txt", timeout=10)
            if r.status_code >= 400:
                rp.parse([])
            else:
                rp.parse(r.text.splitlines())
        except Exception:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(UA, url)


def data_iso(struct):
    if not struct:
        return None
    try:
        return datetime(*struct[:6], tzinfo=timezone.utc).isoformat(timespec="seconds")
    except Exception:
        return None


def si(valore):
    return str(valore).strip().lower() in ("si", "sì", "yes", "true", "1")


# ── lettura delle fonti ────────────────────────────────────────────────────

def da_feed(xml, fonte):
    feed = feedparser.parse(xml)
    voci = []
    for e in feed.entries:
        url = e.get("link")
        if not url:
            continue
        titolo = pulisci(e.get("title"))
        testata = None
        if fonte.get("tipo") == "google":
            src = e.get("source")
            testata = src.get("title") if isinstance(src, dict) else None
            if testata and titolo.endswith(" - " + testata):
                titolo = titolo[: -len(" - " + testata)]
        sommario = pulisci(e.get("summary"), SOMMARIO_MAX)
        if fonte.get("tipo") == "google":
            sommario = ""  # il "sommario" di Google è solo il titolo ripetuto
        voci.append({
            "url": url,
            "titolo": titolo,
            "sommario": sommario,
            "data": data_iso(e.get("published_parsed") or e.get("updated_parsed")),
            "testata": testata,
        })
    return voci


def trova_feed(pagina_html, base):
    try:
        doc = lhtml.fromstring(pagina_html)
    except Exception:
        return None
    for link in doc.xpath('//link[@rel="alternate"]'):
        tipo = (link.get("type") or "").lower()
        if "rss" in tipo or "atom" in tipo:
            href = link.get("href")
            if href:
                return urllib.parse.urljoin(base, href)
    return None


def da_pagina(pagina_html, base, filtro):
    """Prende dalla pagina i link che sembrano notizie."""
    doc = lhtml.fromstring(pagina_html)
    doc.make_links_absolute(base)
    host = urllib.parse.urlparse(base).netloc.replace("www.", "")
    visti, voci = set(), []
    for a in doc.xpath("//a[@href]"):
        url = a.get("href").split("#")[0]
        if not url.startswith("http"):
            continue
        p = urllib.parse.urlparse(url)
        if p.netloc.replace("www.", "") != host:
            continue
        candidati = [pulisci(a.text_content()), pulisci(a.get("title") or "")]
        candidati = [re.sub(r"^(Vai alla notizia|Visualizza la notizia|Visualizza evento|Vai a|Leggi):\s*", "", c, flags=re.I) for c in candidati]
        titolo = max(candidati, key=len)
        if filtro:
            if filtro not in url:
                continue
        else:
            # senza filtro: link interni "profondi" con un titolo vero
            if p.path.count("/") < 2 or len(titolo) < 25:
                continue
        if not titolo:
            # titolo mancante: lo ricavo dall'indirizzo
            ultimo = [x for x in p.path.split("/") if x][-1]
            titolo = ultimo.replace("-", " ").replace("_", " ")
        visti.add(url)
        voci.append({"url": url, "titolo": titolo, "sommario": "", "data": None, "testata": None})
    # se lo stesso link compare più volte, tengo il titolo più lungo
    migliori = {}
    for v in voci:
        if v["url"] not in migliori or len(v["titolo"]) > len(migliori[v["url"]]["titolo"]):
            migliori[v["url"]] = v
    return list(migliori.values())


def leggi_fonte(fonte):
    tipo = fonte.get("tipo", "pagina")
    if tipo == "google":
        q = urllib.parse.urlencode({"q": fonte["cerca"], "hl": "it", "gl": "IT", "ceid": "IT:it"})
        return da_feed(scarica(f"{GNEWS}?{q}").content, fonte)
    if tipo == "rss":
        return da_feed(scarica(fonte["url"]).content, fonte)

    # tipo "pagina": una o più pagine
    pagine = fonte["url"] if isinstance(fonte["url"], list) else [fonte["url"]]
    voci, errori = [], []
    for url in pagine:
        try:
            r = scarica(url)
        except Exception as e:
            errori.append(f"{url}: {e}")
            continue
        if not fonte.get("filtro"):
            feed = trova_feed(r.text, r.url)
            if feed:
                try:
                    voci += da_feed(scarica(feed).content, fonte)
                    continue
                except Exception:
                    pass
        voci += da_pagina(r.text, r.url, fonte.get("filtro"))
    if not voci and errori:
        raise RuntimeError("; ".join(errori))
    return voci


# ── testo completo ─────────────────────────────────────────────────────────

def risolvi_google(url):
    if "news.google.com" not in url:
        return url
    try:
        from googlenewsdecoder import gnewsdecoder
        esito = gnewsdecoder(url, interval=1)
        if esito.get("status") and esito.get("decoded_url"):
            return esito["decoded_url"]
    except Exception:
        pass
    return url


def testo_completo(url):
    """Restituisce (url_vero, testo, data) oppure None."""
    vero = risolvi_google(url)
    if "news.google.com" in vero or vero.lower().endswith(".pdf"):
        return vero, "", None
    if not robots_ok(vero):
        return vero, "", None
    r = scarica(vero)
    testo = trafilatura.extract(r.text, url=vero, include_comments=False,
                                include_tables=True, favor_recall=True) or ""
    data = None
    try:
        meta = trafilatura.extract_metadata(r.text, default_url=vero)
        if meta and meta.date:
            data = meta.date + "T00:00:00+00:00" if len(meta.date) == 10 else meta.date
    except Exception:
        pass
    testo = testo.strip()
    if len(testo) > TESTO_MAX:
        testo = testo[:TESTO_MAX].rsplit(" ", 1)[0] + "…"
    return vero, testo, data


def spiega(e):
    """Messaggio d'errore comprensibile per la pagina 'Stato delle fonti'."""
    if isinstance(e, requests.HTTPError) and e.response is not None:
        codice = e.response.status_code
        if codice == 404:
            return "Pagina non trovata (404): l'indirizzo è cambiato"
        if codice in (401, 403):
            return f"Il sito ha rifiutato l'accesso ({codice})"
        return f"Il sito ha risposto con un errore ({codice})"
    if isinstance(e, requests.Timeout):
        return "Il sito non ha risposto in tempo"
    if isinstance(e, requests.ConnectionError):
        return "Sito non raggiungibile"
    return str(e)[:200]


# ── archivio ───────────────────────────────────────────────────────────────

def carica(percorso, vuoto):
    try:
        with open(percorso, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return vuoto


def salva(percorso, dati):
    os.makedirs(os.path.dirname(percorso), exist_ok=True)
    tmp = percorso + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, percorso)


def main():
    with open(FILE_FONTI, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    fonti = config.get("fonti", [])

    archivio = carica(FILE_ARCHIVIO, {"voci": []})
    voci = {v["id"]: v for v in archivio.get("voci", [])}
    url_noti = {v.get("url_originale") for v in voci.values()} | {v["url"] for v in voci.values()}
    stato_vecchio = {s["nome"]: s for s in carica(FILE_STATO, {"fonti": []}).get("fonti", [])}

    stato, totale_nuovi = [], 0
    for fonte in fonti:
        nome = fonte["nome"]
        voce_stato = {
            "nome": nome,
            "sezione": fonte.get("sezione", "Altro"),
            "tipo": fonte.get("tipo", "pagina"),
            "controllato": adesso(),
            "ultimo_nuovo": stato_vecchio.get(nome, {}).get("ultimo_nuovo"),
        }
        try:
            trovate = leggi_fonte(fonte)
            nuove = [v for v in trovate if ident(v["url"]) not in voci and v["url"] not in url_noti]
            nuove = nuove[:NUOVI_PER_FONTE]
            testi_fatti = 0
            for v in nuove:
                voce = {
                    "id": ident(v["url"]),
                    "url": v["url"],
                    "titolo": v["titolo"],
                    "sommario": v["sommario"],
                    "testo": "",
                    "data": v["data"],
                    "data_stimata": v["data"] is None,
                    "fonte": nome,
                    "testata": v.get("testata"),
                    "sezione": fonte.get("sezione", "Altro"),
                    "raccolto": adesso(),
                }
                if si(fonte.get("testo")) and testi_fatti < TESTI_PER_FONTE:
                    try:
                        vero, testo, data = testo_completo(v["url"])
                        testi_fatti += 1
                        if vero != v["url"]:
                            voce["url_originale"] = v["url"]
                            voce["url"] = vero
                        voce["testo"] = testo
                        if testo and not voce["sommario"]:
                            inizio = testo
                            if inizio.lower().startswith(voce["titolo"].lower()):
                                inizio = inizio[len(voce["titolo"]):]
                            voce["sommario"] = pulisci(inizio, SOMMARIO_MAX)
                        if data and voce["data_stimata"]:
                            voce["data"], voce["data_stimata"] = data, False
                    except Exception as e:
                        print(f"  testo non letto ({v['url']}): {e}", file=sys.stderr)
                    time.sleep(1)
                if not voce["data"]:
                    voce["data"] = voce["raccolto"]
                voci[voce["id"]] = voce
                url_noti.add(v["url"])
            voce_stato.update(esito="ok", trovate=len(trovate), nuove=len(nuove))
            if nuove:
                voce_stato["ultimo_nuovo"] = adesso()
            totale_nuovi += len(nuove)
            print(f"✓ {nome}: {len(trovate)} trovate, {len(nuove)} nuove")
        except Exception as e:
            voce_stato.update(esito="errore", messaggio=spiega(e), trovate=0, nuove=0)
            print(f"✗ {nome}: {e}", file=sys.stderr)
        voce_stato["in_archivio"] = sum(1 for v in voci.values() if v["fonte"] == nome)
        stato.append(voce_stato)
        time.sleep(0.5)

    elenco = sorted(voci.values(), key=lambda v: v.get("data") or "", reverse=True)[:ARCHIVIO_MAX]
    salva(FILE_ARCHIVIO, {"aggiornato": adesso(), "sezioni": config.get("sezioni", []), "voci": elenco})
    salva(FILE_STATO, {"aggiornato": adesso(), "fonti": stato})
    print(f"\nFatto: {totale_nuovi} voci nuove, {len(elenco)} in archivio.")


if __name__ == "__main__":
    main()
