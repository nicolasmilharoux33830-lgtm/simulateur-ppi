import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")

GROUPS = [
    ("Europe", [
        ("^FCHI", "CAC 40"),
        ("^STOXX50E", "Euro Stoxx 50"),
        ("^GDAXI", "DAX"),
        ("^FTSE", "FTSE 100"),
    ]),
    ("États-Unis (clôture)", [
        ("^DJI", "Dow Jones"),
        ("^GSPC", "S&P 500"),
        ("^IXIC", "Nasdaq"),
        ("^VIX", "VIX (peur)"),
    ]),
    ("Futures US (tendance en direct)", [
        ("ES=F", "Future S&P 500"),
        ("NQ=F", "Future Nasdaq"),
        ("YM=F", "Future Dow Jones"),
    ]),
    ("Asie", [
        ("^N225", "Nikkei"),
        ("^HSI", "Hang Seng"),
        ("000001.SS", "Shanghai"),
    ]),
    ("Changes, matières premières, taux", [
        ("EURUSD=X", "EUR/USD"),
        ("BZ=F", "Brent ($)"),
        ("GC=F", "Or ($/oz)"),
        ("^TNX", "Taux US 10 ans (%)"),
        ("BTC-EUR", "Bitcoin (€)"),
    ]),
]

CAC40 = {
    "AC.PA": "Accor", "AI.PA": "Air Liquide", "AIR.PA": "Airbus", "MT.AS": "ArcelorMittal",
    "CS.PA": "AXA", "BNP.PA": "BNP Paribas", "EN.PA": "Bouygues", "BVI.PA": "Bureau Veritas",
    "CAP.PA": "Capgemini", "CA.PA": "Carrefour", "ACA.PA": "Crédit Agricole", "BN.PA": "Danone",
    "DSY.PA": "Dassault Systèmes", "EDEN.PA": "Edenred", "ENGI.PA": "Engie",
    "EL.PA": "EssilorLuxottica", "ERF.PA": "Eurofins", "RMS.PA": "Hermès", "KER.PA": "Kering",
    "OR.PA": "L'Oréal", "LR.PA": "Legrand", "MC.PA": "LVMH", "ML.PA": "Michelin",
    "ORA.PA": "Orange", "RI.PA": "Pernod Ricard", "PUB.PA": "Publicis", "RNO.PA": "Renault",
    "SAF.PA": "Safran", "SGO.PA": "Saint-Gobain", "SAN.PA": "Sanofi", "SU.PA": "Schneider",
    "GLE.PA": "Société Générale", "STLAP.PA": "Stellantis", "STMPA.PA": "STMicro",
    "HO.PA": "Thales", "TTE.PA": "TotalEnergies", "URW.PA": "Unibail", "VIE.PA": "Veolia",
    "DG.PA": "Vinci", "TEP.PA": "Teleperformance",
}


def fetch(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(symbol)}?range=5d&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.load(r)["chart"]["result"][0]
    except Exception:
        return None
    meta = res["meta"]
    closes = [c for c in res["indicators"]["quote"][0].get("close") or [] if c is not None]
    price = meta.get("regularMarketPrice")
    if price is None:
        return None
    pct = meta.get("regularMarketChangePercent")
    if pct is None and len(closes) >= 2:
        pct = (closes[-1] / closes[-2] - 1) * 100
    week = (price / closes[0] - 1) * 100 if closes else None
    when = datetime.fromtimestamp(meta["regularMarketTime"], timezone.utc).astimezone(PARIS)
    return {"price": price, "pct": pct, "week": week, "when": when}


def fmt(v, dec=2):
    return f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")


def sign(v):
    return "n/d" if v is None else ("+" if v >= 0 else "") + fmt(v) + " %"


def main():
    symbols = [s for _, items in GROUPS for s, _ in items] + list(CAC40)
    with ThreadPoolExecutor(max_workers=12) as ex:
        data = dict(zip(symbols, ex.map(fetch, symbols)))

    now = datetime.now(PARIS)
    print(f"DONNÉES DE MARCHÉ (Yahoo Finance) — relevé le {now:%d/%m/%Y à %H:%M} heure de Paris")
    print("Format : dernier cours | variation du jour de cotation indiqué | variation sur 5 séances | date/heure du cours\n")
    for title, items in GROUPS:
        print(f"## {title}")
        for sym, name in items:
            d = data.get(sym)
            if not d:
                print(f"- {name} : indisponible")
                continue
            dec = 4 if sym == "EURUSD=X" else 2
            print(f"- {name} : {fmt(d['price'], dec)} | {sign(d['pct'])} | 5 séances {sign(d['week'])} | {d['when']:%d/%m %H:%M}")
        print()

    movers = sorted(
        ((CAC40[s], data[s]["pct"]) for s in CAC40 if data.get(s) and data[s]["pct"] is not None),
        key=lambda x: x[1],
    )
    if movers:
        print(f"## CAC 40 — plus fortes hausses et baisses de la dernière séance ({len(movers)} valeurs lues)")
        print("Hausses : " + ", ".join(f"{n} {sign(p)}" for n, p in reversed(movers[-3:])))
        print("Baisses : " + ", ".join(f"{n} {sign(p)}" for n, p in movers[:3]))

    if not data.get("^FCHI"):
        sys.exit(1)


if __name__ == "__main__":
    main()
