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


def fiches(cand_files):
    """SIREN -> entité vérifiée + contacts, depuis les fichiers candidats."""
    idx, jours, couv = {}, [], {}
    for f in cand_files:
        if f.endswith("qualifies.json"):
            continue
        c = json.load(open(f))
        jours.append(c["jour"])
        for k, v in c.get("couverture", {}).items():
            couv.setdefault(k, []).append(v)
        ents = [a["entite"] | {"contacts": a.get("contacts", {})} for a in c.get("actes", [])]
        ents += [e for p in c.get("presse", []) for e in p.get("collectivites_citees", [])]
        for e in ents:
            if e.get("siren") and (e["siren"] not in idx or e.get("contacts")):
                idx[e["siren"]] = e
    return idx, sorted(jours), couv


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
        for o in ops:
            e = idx.get(o["siren"]) or o.get("fiche") or {}
            nom, fonction, tel, mail = interlocuteur(e)
            pop = f"{e.get('population'):,} hab.".replace(",", " ") if e.get("population") else ""
            dep = CODES.get(e.get("departement"), "")
            L.append(f"• {e.get('nom', o['siren'])} ({dep}) · {pop}")
            ligne = o["nature"]
            if o.get("date_limite"):
                ligne += f" Réponse avant le {fr_date(o['date_limite'])}."
            L.append(f"  {ligne}")
            L.append(f"  ☎ {nom} ({fonction.lower()}) · {tel} · {mail}")
            L.append(f"  🔗 {o['lien']}")
            total += 1
        L.append("")
    if not total:
        L += ["Aucune collectivité du périmètre à appeler aujourd'hui : pas de besoin d'emprunt "
              "nouveau et vérifiable dans les publications de la veille.", ""]
    L.append("Sources : actes officiels de Bretagne (Mégalis) et du Centre-Val de Loire (GIP RECIA), "
             "BOAMP, TED et presse locale. Pays de la Loire et Normandie : pas d'actes en ligne, "
             "couverts par BOAMP, TED et presse.")
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
    msg = message(q, idx, jours)
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
