"""Planificateur week-end TGVmax Paris <-> bassin de Bordeaux / Arcachon.

Objectif : des ALLERS-RETOURS packagés par week-end, gratuits ou presque.
- Ossature GRATUITE fiable : trains TGVmax (open data officiel SNCF,
  od_happy_card = "OUI"), directs et en correspondance.
- Dernier tronçon non couvert par un train gratuit (ville-pivot -> Bordeaux) :
  on ne peut pas récupérer les prix/places covoiturage/bus en direct
  (pas d'API ouverte, anti-robot), donc on fournit un LIEN BlaBlaCar prêt
  à cliquer + la distance, à vérifier par Nicolas.
Ne réserve jamais rien. Source : https://ressources.data.sncf.com dataset `tgvmax`.
"""
import json
import sys
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")
API = "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/tgvmax/records"

PARIS = "PARIS (intramuros)"
# Zone d'arrivée idéale (bassin de Bordeaux / Arcachon) : hop = 0.
TARGET = {"BORDEAUX ST JEAN": 0, "BIGANOS FACTURE": 0, "ARCACHON": 0}
# Villes-pivots : si un train gratuit n'arrive que là, distance route vers Bordeaux
# (km) + note pour finir le trajet pas cher.
PIVOTS = {
    "LIBOURNE": (30, "TER ~25 min, souvent <10 EUR, tres frequent"),
    "ANGOULEME": (115, "BlaBlaCar/bus ~1h15 (~8-13 EUR) ou TER ~1h"),
    "AGEN": (140, "BlaBlaCar ~1h30 (~10-15 EUR), sud-est de Bordeaux"),
    "DAX": (150, "BlaBlaCar/TER ~1h30, sud de Bordeaux (proche cote)"),
    "NIORT": (175, "BlaBlaCar ~1h45 (~12-16 EUR)"),
    "LA ROCHELLE VILLE": (185, "BlaBlaCar ~2h (~12-18 EUR)"),
    "BAYONNE": (185, "loin (sud) : plutot cote basque"),
    "MONTAUBAN VILLE BOURBON": (215, "loin (sud-est) : surtout vers Toulouse"),
    "POITIERS": (240, "loin : surtout utile comme correspondance train"),
}
# Hubs de correspondance train (decoupage de billet) entre Paris et le Sud-Ouest.
HUBS = ["ST PIERRE DES CORPS", "CHATELLERAULT", "FUTUROSCOPE", "POITIERS", "ANGOULEME", "LIBOURNE"]
CORRIDOR = [PARIS] + sorted(set(HUBS) | set(PIVOTS) | set(TARGET))

SLUG = {
    "PARIS (intramuros)": "paris", "BORDEAUX ST JEAN": "bordeaux",
    "BIGANOS FACTURE": "biganos", "ARCACHON": "arcachon", "LIBOURNE": "libourne",
    "ANGOULEME": "angouleme", "NIORT": "niort", "LA ROCHELLE VILLE": "la-rochelle",
    "POITIERS": "poitiers", "AGEN": "agen", "DAX": "dax", "BAYONNE": "bayonne",
    "MONTAUBAN VILLE BOURBON": "montauban",
}
MIN_LAYOVER, MAX_LAYOVER = 20, 240


def _slug(name):
    if name in SLUG:
        return SLUG[name]
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return s.lower().replace(" ", "-")


def bla_link(frm, to):
    return f"https://www.blablacar.fr/trajets-covoiturage/{_slug(frm)}/{_slug(to)}"


def fetch_day(day):
    stations = "(" + ",".join("'" + s.replace("'", "''") + "'" for s in CORRIDOR) + ")"
    where = (f"date=date'{day}' and axe='ATLANTIQUE' and od_happy_card='OUI' "
             f"and origine in {stations} and destination in {stations}")
    rows, offset = [], 0
    while True:
        qs = urllib.parse.urlencode({"where": where, "limit": 100, "offset": offset,
            "select": "train_no,origine,destination,heure_depart,heure_arrivee,od_happy_card"})
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
        legs.append({"no": x["train_no"], "o": x["origine"], "d": x["destination"], "dep": dep, "arr": arr})
    return legs


def _mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _hm(mins):
    mins %= 24 * 60
    return f"{mins // 60:02d}h{mins % 60:02d}"


def itineraries(legs, origin, dests, dep_min=None, dep_max=None):
    """Itineraires train gratuits origin -> une des dests (direct / 1-2 corresp.)."""
    by_origin = {}
    for lg in legs:
        by_origin.setdefault(lg["o"], []).append(lg)
    dests = set(dests)
    results = []

    def extend(path, station, arr, visited):
        if path and station in dests:
            results.append(list(path))
        if len(path) >= 3:
            return
        for nxt in by_origin.get(station, []):
            if nxt["d"] in visited:          # jamais repasser par une gare deja vue
                continue
            if path:
                wait = nxt["dep"] - arr
                if wait < MIN_LAYOVER or wait > MAX_LAYOVER:
                    continue
            else:
                if dep_min is not None and nxt["dep"] < dep_min:
                    continue
                if dep_max is not None and nxt["dep"] > dep_max:
                    continue
            path.append(nxt)
            extend(path, nxt["d"], nxt["arr"], visited | {nxt["d"]})
            path.pop()

    extend([], origin, 0, {origin})
    seen, uniq = set(), []
    for p in sorted(results, key=lambda p: (p[0]["dep"], p[-1]["arr"])):
        key = tuple((lg["no"], lg["o"], lg["d"]) for lg in p)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def hop_of(station):
    if station in TARGET:
        return 0, None
    return PIVOTS.get(station, (999, None))[0], PIVOTS.get(station, (999, None))[1]


def describe(p, toward_paris):
    """Texte d'un itineraire + info dernier troncon si on s'arrete a un pivot."""
    first, last = p[0], p[-1]
    dur = last["arr"] - first["dep"]
    head = f"{_hm(first['dep'])}->{_hm(last['arr'])} ({dur // 60}h{dur % 60:02d})"
    if len(p) == 1:
        body = f"{head}  TGV {first['no']} [{first['o'].split(' (')[0]}->{first['d']}]"
    else:
        steps = " + ".join(f"{_hm(l['dep'])} {l['o'].split(' (')[0]}->{l['d']} (TGV {l['no']})" for l in p)
        body = f"{head} via {' / '.join(l['d'] for l in p[:-1])}\n       {steps}"
    # pivot (cote Sud-Ouest) = origine si retour, destination si aller
    pivot = first["o"] if toward_paris else last["d"]
    km, note = hop_of(pivot)
    tag = "OK" if km == 0 else f"PIVOT {pivot} (+{km} km Bordeaux)"
    extra = ""
    if km not in (0, 999):
        a, b = ("BORDEAUX ST JEAN", pivot) if toward_paris else (pivot, "BORDEAUX ST JEAN")
        extra = f"\n       -> dernier troncon {a.split(' (')[0]}<->{b.split(' (')[0]} : {note}\n         {bla_link(a, b)}"
    return f"[{tag}] {body}{extra}", km


def rank(options, toward_paris):
    """Trie : d'abord arrivee directe (hop 0), puis plus petit hop, puis horaire."""
    def key(o):
        p = o["path"]
        dur = p[-1]["arr"] - p[0]["dep"]
        dep = p[0]["dep"]
        if toward_paris:   # retour : gratuit > soir (>=18h) > peu de corresp. > court > plus tard
            evening = 0 if dep >= 18 * 60 else 1
            return (o["km"], evening, len(p), dur, -dep)
        return (o["km"], len(p), dur, dep)
    return sorted(options, key=key)


def collect(legs, origin_set, dest_set, toward_paris, dep_min=None, dep_max=None):
    opts = []
    for o in origin_set:
        for p in itineraries(legs, o, dest_set, dep_min, dep_max):
            txt, km = describe(p, toward_paris)
            opts.append({"path": p, "km": km, "txt": txt})
    return rank(opts, toward_paris)


def weekday_fr(d):
    return ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][d.weekday()]


def label(d):
    return f"{weekday_fr(d)} {d.day:02d}/{d.month:02d}"


def block(title, opts, limit=6):
    out = [title]
    if not opts:
        out.append("   (rien de gratuit pour l'instant - les places peuvent s'ouvrir plus tard)")
    for o in opts[:limit]:
        out.append("  - " + o["txt"])
    return "\n".join(out)


def plan_weekend(fri, sat, sun, mon, cache):
    south = list(TARGET) + list(PIVOTS)
    # ALLERS (Paris -> Sud-Ouest)
    al_ven = collect(cache.get(fri, []), [PARIS], south, False, dep_min=17 * 60)
    al_sam = collect(cache.get(sat, []), [PARIS], south, False, dep_max=10 * 60)
    # RETOURS (Sud-Ouest -> Paris) : dimanche prioritaire (ideal le soir, debut
    # d'apres-midi au plus tot) ; lundi matin optionnel.
    re_dim = collect(cache.get(sun, []), south, [PARIS], True, dep_min=13 * 60)
    re_lun = collect(cache.get(mon, []), south, [PARIS], True, dep_max=10 * 60)

    L = [f"=== WEEK-END {label(fri)} -> {label(sun)} / {label(mon)} ==="]

    # Combo conseille : meilleur aller + meilleur retour (idealement 100% gratuit)
    best_out = al_ven[0] if al_ven else (al_sam[0] if al_sam else None)
    best_ret = re_dim[0] if re_dim else (re_lun[0] if re_lun else None)
    L.append("\n>>> COMBO CONSEILLE (le plus proche de ton ideal aller-retour) :")
    if best_out and best_ret:
        fully = (best_out["km"] == 0 and best_ret["km"] == 0)
        L.append("    ALLER  : " + best_out["txt"])
        L.append("    RETOUR : " + best_ret["txt"])
        L.append("    => " + ("100% GRATUIT de bout en bout !" if fully
                              else "gratuit en train + 1 petit troncon pas cher (voir liens)"))
    else:
        L.append("    pas d'aller-retour complet gratuit ce week-end pour l'instant.")
        if best_out:
            L.append("    (aller gratuit possible, mais pas de retour gratuit trouve)")
        if best_ret:
            L.append("    (retour gratuit possible, mais pas d'aller gratuit trouve)")

    L.append("\n  TOUS LES ALLERS gratuits (Paris -> Sud-Ouest) :")
    L.append(block("   * vendredi soir (depart >= 17h) :", al_ven))
    L.append(block("   * samedi matin (depart <= 10h) :", al_sam))
    L.append("\n  TOUS LES RETOURS gratuits (Sud-Ouest -> Paris) :")
    L.append(block("   * dimanche - PRIORITAIRE (depart >= 13h, l'ideal c'est le soir >= 18h) :", re_dim))
    L.append(block("   * lundi matin - OPTIONNEL (depart < 10h) :", re_lun))
    return "\n".join(L)


def main():
    today = datetime.now(PARIS_TZ).date()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    max_day = today + timedelta(days=30)
    fri = today + timedelta((4 - today.weekday()) % 7)
    weekends = []
    for _ in range(n):
        if fri > max_day:
            break
        weekends.append((fri, fri + timedelta(1), fri + timedelta(2), fri + timedelta(3)))
        fri = fri + timedelta(7)
    days = sorted({x for w in weekends for x in w if x <= max_day})

    def safe_fetch(d):
        try:
            return fetch_day(d)
        except Exception as e:
            print(f"[avert] {d}: {e}", file=sys.stderr)
            return []

    with ThreadPoolExecutor(max_workers=8) as ex:
        cache = dict(zip(days, ex.map(safe_fetch, days)))
    print(f"TGVmax week-end Paris <-> Bordeaux/Arcachon - releve {datetime.now(PARIS_TZ):%d/%m %H:%M}")
    print("(trains GRATUITS open data SNCF ; [OK]=arrive dans le bassin, [PIVOT]=+ petit troncon pas cher)")
    print("Bassin d'Arcachon : depuis Bordeaux, TER vers Biganos ~45 min.\n")
    for (fri, sat, sun, mon) in weekends:
        print(plan_weekend(fri, sat, sun, mon, cache))
        print("\n" + "-" * 58 + "\n")


if __name__ == "__main__":
    main()
