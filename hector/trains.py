"""Planificateur TGVmax Paris <-> Bordeaux / Biganos (données open data SNCF).

Source officielle : https://ressources.data.sncf.com dataset `tgvmax`
(od_happy_card = "OUI" => place TGVmax gratuite ouverte à la réservation).
Ne réserve rien : affiche seulement les trajets gratuits possibles,
directs ou en correspondance (découpage de billet).
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")
API = "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/tgvmax/records"

# Gares du corridor Atlantique utiles (nom exact dans le dataset), du nord au sud.
PARIS = "PARIS (intramuros)"
BORDEAUX = "BORDEAUX ST JEAN"
BIGANOS = "BIGANOS FACTURE"
ARCACHON = "ARCACHON"
# Hubs de correspondance entre Paris et Bordeaux (ordre géographique).
HUBS = ["ST PIERRE DES CORPS", "CHATELLERAULT", "FUTUROSCOPE", "POITIERS",
        "ANGOULEME", "LIBOURNE"]
CORRIDOR = [PARIS] + HUBS + [BORDEAUX, BIGANOS, ARCACHON]

MIN_LAYOVER = 20     # minutes mini pour une correspondance
MAX_LAYOVER = 240    # minutes maxi (au-delà, trajet peu réaliste)


def fetch_day(day):
    """Tous les tronçons TGVmax du corridor Atlantique pour une date."""
    stations = "(" + ",".join("'" + s.replace("'", "''") + "'" for s in CORRIDOR) + ")"
    where = (f"date=date'{day}' and axe='ATLANTIQUE' "
             f"and origine in {stations} and destination in {stations}")
    rows, offset = [], 0
    while True:
        qs = urllib.parse.urlencode({
            "where": where, "limit": 100, "offset": offset,
            "select": "train_no,origine,destination,heure_depart,heure_arrivee,od_happy_card",
        })
        req = urllib.request.Request(API + "?" + qs, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        batch = data.get("results", [])
        rows.extend(batch)
        offset += len(batch)
        if len(batch) < 100 or offset >= data.get("total_count", 0) or offset >= 9900:
            break
    legs = []
    for x in rows:
        if x.get("od_happy_card") != "OUI":
            continue
        dep, arr = _mins(x["heure_depart"]), _mins(x["heure_arrivee"])
        if arr < dep:
            arr += 24 * 60
        legs.append({"no": x["train_no"], "o": x["origine"], "d": x["destination"],
                     "dep": dep, "arr": arr})
    return legs


def _mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hm(mins):
    mins %= 24 * 60
    return f"{mins // 60:02d}h{mins % 60:02d}"


def itineraries(legs, origin, dest, dep_min=None, dep_max=None):
    """Itinéraires gratuits origin->dest : direct, 1 ou 2 correspondances."""
    by_origin = {}
    for lg in legs:
        by_origin.setdefault(lg["o"], []).append(lg)
    results = []

    def extend(path, current_station, current_arr):
        if current_station == dest and path:
            results.append(list(path))
            return
        if len(path) >= 3:   # 3 tronçons max (2 correspondances)
            return
        for nxt in by_origin.get(current_station, []):
            if path:  # contrainte de correspondance
                wait = nxt["dep"] - current_arr
                if wait < MIN_LAYOVER or wait > MAX_LAYOVER:
                    continue
            else:     # premier tronçon : fenêtre de départ
                if dep_min is not None and nxt["dep"] < dep_min:
                    continue
                if dep_max is not None and nxt["dep"] > dep_max:
                    continue
            if any(p["no"] == nxt["no"] for p in path):
                continue
            # on n'enchaîne pas deux tronçons qui repartent en arrière (évite boucles)
            path.append(nxt)
            extend(path, nxt["d"], nxt["arr"])
            path.pop()

    extend([], origin, 0)
    # dédoublonnage + tri par heure de départ puis durée
    seen, uniq = set(), []
    for p in sorted(results, key=lambda p: (p[0]["dep"], p[-1]["arr"])):
        key = tuple(lg["no"] for lg in p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def fmt_itin(p):
    first, last = p[0], p[-1]
    dur = last["arr"] - first["dep"]
    head = f"{_hm(first['dep'])}->{_hm(last['arr'])} ({dur // 60}h{dur % 60:02d})"
    if len(p) == 1:
        return f"  DIRECT {head}  TGV {first['no']}  [{first['o']} -> {first['d']}]"
    steps = "  +  ".join(
        f"{_hm(lg['dep'])} {lg['o']}->{lg['d']} ({_hm(lg['arr'])}, TGV {lg['no']})" for lg in p)
    chg = " via " + " / ".join(lg["d"] for lg in p[:-1])
    return f"  CORRESP.{chg} {head}\n      {steps}"


def section(title, legs, origin, dests, dep_min=None, dep_max=None, limit=8):
    out = [title]
    allp = []
    for dest in dests:
        allp += itineraries(legs, origin, dest, dep_min, dep_max)
    allp.sort(key=lambda p: (p[0]["dep"], p[-1]["arr"]))
    if not allp:
        out.append("  (aucune place TGVmax gratuite trouvée sur ce créneau)")
    for p in allp[:limit]:
        out.append(fmt_itin(p))
    return "\n".join(out)


def weekday_fr(d):
    return ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][d.weekday()]


def next_weekend(today):
    """Vendredi/samedi/dimanche/lundi du prochain week-end (>= aujourd'hui)."""
    fri = today + timedelta((4 - today.weekday()) % 7)
    return fri, fri + timedelta(1), fri + timedelta(2), fri + timedelta(3)


def label(d):
    return f"{weekday_fr(d)} {d.day:02d}/{d.month:02d}"


def plan_weekend(fri, sat, sun, mon, cache):
    L = []
    L.append(f"=== WEEK-END : {label(fri)} -> {label(sun)}/{label(mon)} ===\n")

    # ALLER : vendredi soir apres 17h
    L.append(section(f"ALLER {label(fri)} - Paris (Montparnasse), depart >= 17h00 :",
                     cache[fri], PARIS, [BORDEAUX, BIGANOS, ARCACHON], dep_min=17 * 60))
    L.append("")
    # ALLER : samedi tot le matin
    L.append(section(f"ALLER {label(sat)} - Paris (Montparnasse), depart tot (<= 10h00) :",
                     cache[sat], PARIS, [BORDEAUX, BIGANOS, ARCACHON], dep_max=10 * 60))
    L.append("")
    # RETOUR : dimanche soir apres 18h
    L.append(section(f"RETOUR {label(sun)} - vers Paris, depart >= 18h00 :",
                     cache[sun], BORDEAUX, [PARIS], dep_min=18 * 60) + "\n"
             + section(f"RETOUR {label(sun)} - depuis Biganos, depart >= 18h00 :",
                       cache[sun], BIGANOS, [PARIS], dep_min=18 * 60))
    L.append("")
    # RETOUR : lundi matin avant 10h
    L.append(section(f"RETOUR {label(mon)} - vers Paris, depart < 10h00 :",
                     cache[mon], BORDEAUX, [PARIS], dep_max=10 * 60) + "\n"
             + section(f"RETOUR {label(mon)} - depuis Biganos, depart < 10h00 :",
                       cache[mon], BIGANOS, [PARIS], dep_max=10 * 60))
    return "\n".join(L)


def main():
    today = datetime.now(PARIS_TZ).date()
    # nombre de week-ends à couvrir (par défaut 2) ; données SNCF ~30 jours
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    max_day = today + timedelta(days=30)

    weekends = []
    fri, sat, sun, mon = next_weekend(today)
    for _ in range(n):
        if fri > max_day:
            break
        weekends.append((fri, sat, sun, mon))
        fri, sat, sun, mon = (d + timedelta(7) for d in (fri, sat, sun, mon))

    needed = sorted({d for w in weekends for d in w if d <= max_day})
    cache = {}
    for d in needed:
        try:
            cache[d] = fetch_day(d)
        except Exception as e:
            cache[d] = []
            print(f"[avertissement] récupération {d} échouée : {e}", file=sys.stderr)

    print(f"TGVmax Paris <-> Bordeaux/Biganos — relevé {datetime.now(PARIS_TZ):%d/%m/%Y %H:%M} "
          f"(source open data SNCF, places gratuites uniquement)\n")
    for (fri, sat, sun, mon) in weekends:
        print(plan_weekend(fri, sat, sun, mon, cache))
        print("\n" + "-" * 60 + "\n")


if __name__ == "__main__":
    main()
