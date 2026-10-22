"""Construit le rapport « Qui appeler » (Telegram) et les lignes du Google Sheets.

Usage : python3 rapport.py qualifies.json candidats1.json [candidats2.json ...]
        [--sortie message.txt] [--webhook URL --secret SECRET]

qualifies.json (rédigé par Hector après lecture des actes) :
{"opportunites": [{"niveau": "A|B|C", "siren": "...", "nature": "...", "montant": 12345.0 | null,
                   "statut": "...", "date_publication": "AAAA-MM-JJ", "date_limite": "AAAA-MM-JJ" | null,
                   "source": "...", "lien": "..."}],
 "ecartes": [{"siren": "...", "nom": "...", "acte": "...", "date_publication": "AAAA-MM-JJ",
              "motif": "...", "lien": "..."}]}
Identité, population, département et coordonnées sont repris des candidats vérifiés (pas de saisie).
"""
import json
import sys
import urllib.request
from datetime import date, datetime
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
NIVEAUX = [("A", "🔴", "Consultation bancaire en cours"), ("B", "🟠", "Emprunt prévu, banque à trouver"),
           ("C", "⚪", "Signaux à suivre")]
CODES = {"Loire-Atlantique": "44", "Maine-et-Loire": "49", "Mayenne": "53", "Sarthe": "72", "Vendée": "85",
         "Côtes-d'Armor": "22", "Finistère": "29", "Ille-et-Vilaine": "35", "Morbihan": "56", "Cher": "18",
         "Eure-et-Loir": "28", "Indre": "36", "Indre-et-Loire": "37", "Loir-et-Cher": "41", "Loiret": "45",
         "Calvados": "14", "Eure": "27", "Manche": "50", "Orne": "61", "Seine-Maritime": "76"}


def args():
    a = sys.argv[1:]
    opts = {}
    for k in ("--sortie", "--webhook", "--secret"):
        if k in a:
            i = a.index(k)
            opts[k] = a[i + 1]
            del a[i:i + 2]
    return a[0], a[1:], opts


LIBELLE_SOURCE = {"Mégalis Bretagne": "Mégalis Bretagne, registre officiel des actes transmis en préfecture",
                  "GIP RECIA (Centre-Val de Loire)": "GIP RECIA, registre officiel des actes transmis en préfecture"}
LIENS = {}


def fiches(cand_files):
    """SIREN -> entité vérifiée (contacts, finances) ; lien -> horodatage de publication."""
    idx, jours, couv = {}, [], {}
    for f in cand_files:
        if f.endswith("qualifies.json"):
            continue
        c = json.load(open(f))
        jours.append(c["jour"])
        for k, v in c.get("couverture", {}).items():
            couv.setdefault(k, []).append(v)
        ents = []
        for a in c.get("actes", []):
            ents.append(a["entite"] | {"contacts": a.get("contacts", {}), "finances": a.get("finances")})
            info = {"publie_le": a.get("publie_le"), "date_acte": a.get("date_acte"),
                    "plateforme": LIBELLE_SOURCE.get(a["source"], a["source"]), "objet": a.get("objet"),
                    "budget": a.get("budget_emprunt")}
            for u in [a["lien"]] + a.get("annexes", []):
                LIENS[u] = info
        for p in c.get("presse", []):
            ents += p.get("collectivites_citees", [])
            LIENS[p["lien"]] = {"publie_le": p.get("date_publication"), "plateforme": p.get("media")}
        for b in c.get("boamp", []) + c.get("ted", []):
            LIENS[b["lien"]] = {"publie_le": b.get("date_publication"), "plateforme": b["source"]}
        for e in ents:
            if e.get("siren") and (e["siren"] not in idx or e.get("contacts")):
                idx[e["siren"]] = e
    return idx, sorted(jours), couv


def court(x):
    x = float(x)
    if abs(x) >= 1e6:
        return f"{x / 1e6:,.2f} M€".replace(",", " ").replace(".", ",")
    if abs(x) >= 1e4:
        return f"{x / 1e3:,.0f} k€".replace(",", " ")
    return f"{x:,.0f} €".replace(",", " ")


def ligne_finances(f):
    if not f or f.get("erreur") or "encours" not in f:
        return []
    hab = f"{f.get('encours_hab') or 0:,.0f}".replace(",", " ")
    p = [f"dette {court(f['encours'])} ({hab} €/hab)"]
    if f.get("desendettement_ans") is not None:
        p.append(f"désendettement {str(f['desendettement_ans']).replace('.', ',')} ans")
    if f.get("epargne_brute") is not None:
        t = f" ({str(f['taux_epargne_brute']).replace('.', ',')} % des recettes)" if f.get("taux_epargne_brute") is not None else ""
        p.append(f"épargne brute {court(f['epargne_brute'])}{t}")
    if f.get("depenses_equipement") is not None:
        p.append(f"investissement {court(f['depenses_equipement'])}")
    if f.get("emprunts_annee") is not None:
        p.append(f"emprunté dans l'année {court(f['emprunts_annee'])}" if f["emprunts_annee"] >= 1
                 else "aucun emprunt dans l'année")
    if f.get("tresorerie") is not None:
        p.append(f"trésorerie {court(f['tresorerie'])}")
    out = [f"📊 Comptes {f['annee']} (OFGL) : " + ", ".join(p) + "."]
    a = f.get("budget_annexe") or {}
    if a.get("budget") and a.get("capacite_financement") is not None:
        cf = a["capacite_financement"]
        q = [("besoin de financement " if cf < 0 else "capacité de financement ") + court(abs(cf))]
        if a.get("epargne_brute") is not None:
            q.append(f"épargne brute {court(a['epargne_brute'])}")
        if a.get("fonds_roulement") is not None:
            q.append(f"fonds de roulement {court(a['fonds_roulement'])}")
        if a.get("encours") is not None:
            q.append(f"dette {court(a['encours'])}" if a["encours"] >= 1 else "aucune dette")
        out.append(f"   Budget {a['budget'].title()} {f['annee']} : " + ", ".join(q) + ".")
    return out


def date_heure(s):
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%d/%m à %Hh%M") if len(s) > 10 else dt.strftime("%d/%m")
    except ValueError:
        return s


def fr_date(s):
    return date.fromisoformat(s[:10]).strftime("%d/%m/%Y") if s else ""


def euros(x):
    if x in (None, ""):
        return ""
    return f"{float(x):,.2f} €".replace(",", " ").replace(".", ",").replace(",00 €", " €")


def periode(jours):
    a, b = date.fromisoformat(jours[0]), date.fromisoformat(jours[-1])
    return f"du {a:%d/%m}" if a == b else f"du {a:%d/%m} au {b:%d/%m}"


def interlocuteur(e):
    c = e.get("contacts") or {}
    nom = c.get("elu") or "Non trouvé"
    fonction = (c.get("elu_fonction") or "").strip() or ("Maire" if e.get("type") == "Commune" else "Président")
    return nom, fonction, c.get("telephone") or "Non trouvé", c.get("email") or "Non trouvé"


def message(q, idx, jours):
    today = datetime.now(PARIS).date()
    L = [f"📞 Hector · Qui appeler ce matin ({today:%d/%m})",
         f"Emprunts des communes et intercommunalités · publications {periode(jours)}", ""]
    total = 0
    for niv, puce, titre in NIVEAUX:
        ops = [o for o in q.get("opportunites", []) if o.get("niveau") == niv]
        if not ops:
            continue
        L.append(f"{puce} {niv} · {titre} ({len(ops)})")
        L.append("")
        for o in ops:
            e = idx.get(o["siren"]) or o.get("fiche") or {}
            nom, fonction, tel, mail = interlocuteur(e)
            dep = e.get("departement", "")
            pop = f"{e.get('population'):,}".replace(",", " ") if e.get("population") else "?"
            typ = (e.get("type") or "collectivité").lower()
            L.append(f"▶ {e.get('nom', o['siren']).upper()} · {dep} ({CODES.get(dep, '')})")
            L.append(f"   {typ} de {pop} hab. (INSEE {e.get('annee_population', '2023')}) · SIREN {o['siren']}")
            info = LIENS.get(o["lien"], {})
            quand = o.get("publie_le") or info.get("publie_le")
            acte = o.get("date_acte") or info.get("date_acte")
            src = info.get("plateforme") or o.get("source", "")
            ligne = f"📅 Publié le {date_heure(quand)}" if quand else "📅 Publication"
            ligne += f" sur {src}" if src else ""
            if acte:
                ligne += f". Acte daté du {fr_date(acte)}"
            L.append(ligne + ".")
            besoin = o["nature"]
            if o.get("date_limite"):
                besoin += f" Réponse avant le {fr_date(o['date_limite'])}."
            L.append(f"💶 {besoin}")
            if o.get("extrait"):
                L.append(f"📝 Extrait de l'acte : « {o['extrait']} »")
            b = info.get("budget") or {}
            for lg in b.get("lignes", []):
                doc = f"{b.get('natdec') or 'Budget'}" + (f" n°{b['numdec']}" if b.get("numdec") else "")
                real = euros(lg["realise"]) if lg["realise"] else "non indiqué"
                L.append(f"🧾 Fichier budgétaire officiel ({doc} {b.get('exer', '')}, {(b.get('budget') or '').title()}) : "
                         f"compte {lg['compte']} Emprunts en recettes, prévu {euros(lg['budget_total'])}, réalisé {real}.")
            L += ligne_finances(e.get("finances"))
            site = (e.get("contacts") or {}).get("site")
            L.append(f"☎ {nom}, {fonction.lower()} · {tel} · {mail}" + (f" · {site}" if site else ""))
            L.append(f"🔗 {o['lien']}")
            L.append("")
            total += 1
    if not total:
        L += ["Personne à appeler ce matin : aucun besoin d'emprunt nouveau et vérifiable "
              "dans les publications de la veille.", ""]
    return "\n".join(L)


def bloc_lecture(couv, jours):
    L = [f"🔎 Ce qu'Hector a lu ({periode(jours)}) :"]
    for k, v in couv.items():
        if k != "Référentiel":
            L.append(f"• {k} : {' / '.join(v)}")
    L.append("• Pays de la Loire et Normandie : pas de registre public des actes, couverts par BOAMP, TED et presse.")
    L.append("• Contrôles : population INSEE, SIREN (Annuaire des entreprises), élus (Répertoire national des élus), "
             "coordonnées (Annuaire de l'administration), comptes (OFGL).")
    return "\n".join(L)


def lignes_sheet(q, idx, jours, couv):
    detect = datetime.now(PARIS).strftime("%d/%m/%Y")
    opp, ec = [], []
    for o in q.get("opportunites", []):
        e = idx.get(o["siren"]) or o.get("fiche") or {}
        nom, fonction, tel, mail = interlocuteur(e)
        opp.append([detect, e.get("region", ""), e.get("departement", ""), CODES.get(e.get("departement"), ""),
                    e.get("type", ""), (e.get("contacts") or {}).get("nom_officiel") or e.get("nom", ""),
                    e.get("population", ""), e.get("annee_population", ""), o["siren"], nom, fonction, tel, mail,
                    o["nature"], o.get("montant") if o.get("montant") is not None else "", o["niveau"],
                    o.get("statut", ""), fr_date(o.get("date_publication")), fr_date(o.get("date_limite")),
                    o.get("source", ""), o["lien"], "Non", ""])
    for x in q.get("ecartes", []):
        e = idx.get(x.get("siren"), {})
        dep = e.get("departement")
        ec.append([detect, x.get("nom") or e.get("nom", ""), x.get("siren", ""),
                   f"{dep} ({CODES.get(dep, '')})" if dep else "", x.get("acte", ""),
                   fr_date(x.get("date_publication")), x.get("motif", ""), x.get("lien", "")])
    ouvertes = sum(1 for o in q.get("opportunites", []) if o.get("niveau") == "A")
    regions = {}
    for o in q.get("opportunites", []):
        e = idx.get(o["siren"]) or o.get("fiche") or {}
        regions.setdefault(e.get("region", "?"), {}).setdefault(e.get("departement", "?"), 0)
        regions[e.get("region", "?")][e.get("departement", "?")] += 1
    rep = " ".join(f"{r} : {sum(d.values())} ({', '.join(f'{k} {v}' for k, v in d.items())})."
                   for r, d in regions.items()) or "Aucune opportunité."
    sources = " ".join(f"{k} : {' / '.join(v)}." for k, v in couv.items())
    f = "INDIRECT(\"A\"&ROW())"
    journal = [[detect, f"Publications {periode(jours)}", f"=COUNTIF('Opportunités'!$A:$A,{f})",
                f"=COUNTIFS('Opportunités'!$A:$A,{f},'Opportunités'!$P:$P,\"A\")",
                f"=COUNTIFS('Opportunités'!$A:$A,{f},'Opportunités'!$P:$P,\"B\")",
                f"=COUNTIFS('Opportunités'!$A:$A,{f},'Opportunités'!$P:$P,\"C\")",
                ouvertes, rep, sources,
                "Pays de la Loire et Normandie : pas de plateforme publique des actes, couverture BOAMP, TED et presse. "
                "Presse lue sur les titres seulement (sites inaccessibles aux outils d'IA).",
                q.get("suivi", "")]]
    return {"Opportunités": opp, "Actes écartés": ec, "Journal de veille": journal}


def main():
    qf, cfs, opts = args()
    q = json.load(open(qf))
    idx, jours, couv = fiches(cfs)
    msg = message(q, idx, jours) + "\n" + bloc_lecture(couv, jours)
    if "--sortie" in opts:
        open(opts["--sortie"], "w").write(msg)
    print(msg)
    if "--webhook" in opts:
        body = json.dumps({"secret": opts.get("--secret", ""), "lignes": lignes_sheet(q, idx, jours, couv)}).encode()
        req = urllib.request.Request(opts["--webhook"], data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            print("\nGoogle Sheets :", r.read().decode()[:500])


if __name__ == "__main__":
    main()
