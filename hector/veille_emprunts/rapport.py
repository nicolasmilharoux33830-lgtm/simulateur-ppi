"""Construit le rapport « Qui appeler » (Telegram) et les lignes du Google Sheets.

Usage : python3 rapport.py qualifies.json candidats1.json [candidats2.json ...]
        [--sortie message.txt] [--objectif 7] [--calcules 5] [--surs] [--webhook URL --secret SECRET]

--surs : seulement les collectivités dont un document dit qu'elles vont emprunter (A et B), sans liste calculée.

Deux listes :
- « Ont décidé d'emprunter » : niveaux A et B qualifiés par Hector (acte, consultation, article, site) ;
- « Vont emprunter » : le calcul (modèle économétrique + chantier lancé + trésorerie) complète jusqu'à
  l'objectif du matin, avec au moins --calcules noms.

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
import urllib.parse
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
    opts = {"--surs": "--surs" in a}
    a = [x for x in a if x != "--surs"]
    for k in ("--sortie", "--webhook", "--secret", "--top", "--objectif", "--calcules"):
        if k in a:
            i = a.index(k)
            opts[k] = a[i + 1]
            del a[i:i + 2]
    return a[0], a[1:], opts


LIBELLE_SOURCE = {"Mégalis Bretagne": "Mégalis Bretagne, registre officiel des actes transmis en préfecture",
                  "GIP RECIA (Centre-Val de Loire)": "GIP RECIA, registre officiel des actes transmis en préfecture"}
LIENS = {}
ECARTS_AUTO = []
TRAVAUX = {}
SURPLUS = []
ECHEANCES = {}
RECENTS = {}
VIVIER = 100


def fiches(cand_files):
    """SIREN -> entité vérifiée (contacts, finances, prédiction) ; lien -> horodatage de publication."""
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
            ents.append(a["entite"])
            info = {"publie_le": a.get("publie_le"), "date_acte": a.get("date_acte"),
                    "plateforme": LIBELLE_SOURCE.get(a["source"], a["source"]), "objet": a.get("objet"),
                    "budget": a.get("budget_emprunt")}
            for u in [a["lien"]] + a.get("annexes", []):
                LIENS[u] = info
            if a.get("motif_ecart") and a["entite"].get("eligible"):
                ECARTS_AUTO.append({"siren": a["siren"], "nom": a["entite"].get("nom"), "acte": a.get("objet"),
                                    "date_publication": c["jour"], "motif": a["motif_ecart"], "lien": a["lien"]})
        for p in c.get("presse", []):
            ents += p.get("collectivites_citees", [])
            info = {"publie_le": p.get("publie_le"), "plateforme": p.get("media_nom") or p.get("media")}
            LIENS[p["lien"]] = info
            if p.get("lien_article"):
                LIENS[p["lien_article"]] = info
        for b in c.get("consultations", []) + c.get("boamp", []) + c.get("ted", []):
            if b.get("entite", {}).get("siren"):
                ents.append(b["entite"])
            LIENS[b["lien"]] = {"publie_le": b.get("date_publication"), "plateforme": b["source"]}
        for siren, v in (c.get("travaux") or {}).items():
            TRAVAUX.setdefault(siren, []).extend(v)
        for e in c.get("echeances") or []:
            ECHEANCES.setdefault(e["siren"], e)
            ents.append(e["entite"])
        for siren, v in (c.get("emprunts_recents") or {}).items():
            RECENTS.setdefault(siren, []).extend(v)
        for p in c.get("sites", []):
            ents.append(p["entite"])
            LIENS[p["url"]] = {"publie_le": p.get("mis_en_ligne"), "date_acte": p.get("date_seance"),
                               "plateforme": "le site de la collectivité"}
        for e in ents:
            if e.get("siren") and e["siren"] not in idx:
                idx[e["siren"]] = dict(e)
        for siren, fi in (c.get("fiches") or {}).items():
            idx.setdefault(siren, {"siren": siren}).update(fi)
    return idx, sorted(jours), couv


def ligne_prediction(p):
    if not p:
        return []
    pc = round(float(p["proba"]) * 100)
    txt = (f"🔮 Probabilité d'emprunter en {p['annee_prevue']} (modèle sur les comptes {p['annee_comptes']}) : {pc} %, "
           f"rang {p['rang_departement']} du département")
    if p.get("facteurs"):
        txt += f" · {p['facteurs']}"
    return [txt + "."]


def fiche_de(o, idx):
    """Entité vérifiée d'une opportunité : candidats.json, complété par la fiche jointe par Hector."""
    e = dict(o.get("fiche") or {})
    for k, v in (idx.get(o["siren"]) or {}).items():
        if v or k not in e:
            e[k] = v
    return e


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


def hab(n):
    return f"{int(n):,}".replace(",", " ") if n not in (None, "") else "?"


def entete(e, siren):
    dep = e.get("departement") or ""
    code = CODES.get(dep) or e.get("dept") or ""
    typ = "EPCI" if e.get("type") == "EPCI" else "commune"
    return f"{(e.get('nom') or siren).upper()} ({code}) · {typ} de {hab(e.get('population'))} hab."


def contact(e):
    nom, fonction, tel, mail = interlocuteur(e)
    return f"   ☎ {nom}, {fonction.lower()} · {tel} · {mail}"


def proba(p):
    if not p:
        return ""
    t = f"{round(float(p['proba']) * 100)} % en {p['annee_prevue']}"
    if p.get("proba_annee_suivante"):
        t += f", {round(float(p['proba_annee_suivante']) * 100)} % en {int(p['annee_prevue']) + 1}"
    if p.get("proba_2_mois"):
        t += f" · {round(float(p['proba_2_mois']) * 100)} % d'ici 2 mois"
    return t


def message(q, idx, jours, calc, surs=False):
    today = datetime.now(PARIS).date()
    ops = [o for o in q.get("opportunites", []) if o.get("niveau") in ("A", "B")]
    ops.sort(key=lambda o: (o["niveau"], -float(((fiche_de(o, idx).get("prediction") or {}).get("proba")) or 0)))
    suivis = [] if surs else [o for o in q.get("opportunites", []) if o.get("niveau") == "C"]
    n = len(ops) + len(calc)
    if surs:
        L = [f"📞 Hector · {today:%d/%m} · {n} collectivité{'s' if n > 1 else ''} qui {'vont' if n > 1 else 'va'} emprunter", ""]
        if not ops:
            a, b = date.fromisoformat(jours[0]), date.fromisoformat(jours[-1])
            quand = f"le {a:%d/%m}" if a == b else f"entre le {a:%d/%m} et le {b:%d/%m}"
            L += [f"Aucune collectivité n'a écrit {quand} qu'elle va emprunter sans avoir déjà choisi sa banque.", ""]
    else:
        L = [f"📞 Hector · {today:%d/%m} · {n} collectivité{'s' if n > 1 else ''} à appeler", ""]
    i = 0
    if ops:
        L.append(f"✅ C'EST ÉCRIT : ILS VONT EMPRUNTER ({len(ops)})" if surs else f"✅ ONT DÉCIDÉ D'EMPRUNTER ({len(ops)})")
        for o in ops:
            i += 1
            e = fiche_de(o, idx)
            info = LIENS.get(o["lien"], {})
            L.append(f"{i}. {'🔴' if o['niveau'] == 'A' else '🟠'} {entete(e, o['siren'])}")
            besoin = o["nature"]
            if o.get("date_limite"):
                besoin += f" Réponse avant le {fr_date(o['date_limite'])}."
            L.append(f"   {besoin}")
            quand = o.get("publie_le") or info.get("publie_le")
            src = o.get("source") or info.get("plateforme") or ""
            if o.get("extrait"):
                L.append(f"   📝 « {o['extrait']} »")
            L.append(f"   📅 {src}" + (f", publié le {date_heure(quand)}" if quand else ""))
            L.append(contact(e))
            L.append(f"   🔗 {o['lien']}")
        L.append("")
    if calc:
        L.append(f"📈 VONT EMPRUNTER · calcul économétrique ({len(calc)})")
        for c in calc:
            i += 1
            L.append(f"{i}. {entete(c['entite'], c['siren'])} · {proba(c['prediction'])}")
            L.append(f"   {c['declencheur']}")
            L.append(f"   {c['finances']}")
            L.append(contact(c["entite"]))
            if c.get("lien"):
                L.append(f"   🔗 {c['lien']}")
        L.append("")
    if SURPLUS and not surs:
        def court_dec(p):
            r, genre = p[2], p[6]
            quoi = {"ligne": "ligne de trésorerie", "emprunt": "emprunt annuel", "chantier": "chantier"}.get(genre, "modèle")
            return f"{r['nom']} ({r['dept']}, {quoi})"
        L.append(f"➕ AUSSI PROBABLES ({len(SURPLUS)}) : " + " · ".join(court_dec(p) for p in SURPLUS))
        L.append("")
    if suivis:
        L.append(f"👀 À SUIVRE ({len(suivis)}) : " + " · ".join(
            f"{(fiche_de(o, idx).get('nom') or o['siren'])} ({o.get('statut') or 'signal'})" for o in suivis))
        L.append("")
    if not n and not surs:
        L += ["Personne à appeler ce matin.", ""]
    return "\n".join(L)


def une_fois(siren, ecart, debut, duree):
    """Vrai le jour (à 2 jours près, pour les week-ends) où cette collectivité doit être proposée :
    chacune passe une seule fois dans la fenêtre [debut, debut + duree], à une date qui lui est propre."""
    cible = debut + int(siren[-6:]) % duree
    return cible - 2 <= ecart <= cible


def liste_calculee(n, exclus, jour_ref):
    """Collectivités éligibles qui vont emprunter selon le calcul, par ordre de fiabilité :
    1. échéance : ligne de trésorerie ou emprunt de l'an dernier arrivant à sa date anniversaire ;
    2. chantier lancé récemment (BOAMP) ;
    3. probabilité annuelle du modèle (comptes OFGL), par roulement parmi les 100 meilleures.
    Chaque piste vient avec le taux observé sur l'historique breton (Mégalis 2021-2026)."""
    import csv
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import veille
    try:
        import imminence
        taux_obs = imminence.TAUX
    except ImportError:
        imminence = None
        taux_obs = {"ligne": 0.41, "emprunt": 0.22, "travaux_90j": 0.29}
    chemin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scores.csv")
    if not os.path.exists(chemin) or n <= 0:
        return []
    scores = {r["siren"]: r for r in csv.DictReader(open(chemin, encoding="utf-8"), delimiter=";")}

    def eligible(r):
        return int(r["population"] or 0) < (10000 if r["type"] == "Commune" else 20000)

    def recent(siren):
        return bool(RECENTS.get(siren))

    mod_mensuel = None
    try:
        mod_mensuel = json.load(open(os.path.join(os.path.dirname(chemin), "imminence.json")))
    except Exception:
        pass

    def proche(r):
        """Probabilité d'une délibération d'emprunt dans les 2 prochains mois (modèle mensuel)."""
        if not mod_mensuel or imminence is None or "x_treso_j" not in r:
            return 0.0
        ann = {k: r.get(f"x_{k}") for k in imminence.ANNUELLES}
        dates_tv = [t["date"] for t in TRAVAUX.get(r["siren"], [])]
        r["proba_2_mois"] = round(imminence.proba_periode(mod_mensuel, ann, dates_tv, jour_ref, 2), 3)
        return r["proba_2_mois"]

    pistes = []
    # 1. échéances
    for siren, e in (ECHEANCES.items() if imminence else []):
        if siren in exclus or recent(siren) or siren not in scores:
            continue
        ecart = (date.fromisoformat(e["attendu"]) - jour_ref).days
        if not une_fois(siren, ecart, 7, 21):
            continue
        taux = taux_obs[e["genre"]]
        if e["genre"] == "ligne":
            dec = (f"🔁 Ligne de trésorerie du {fr_date(e['dernier_acte'])} : renouvellement attendu vers le "
                   f"{fr_date(e['attendu'])[:5]} ({round(taux * 100)} % renouvellent à la date anniversaire)")
        else:
            dec = (f"📅 Emprunt du {fr_date(e['dernier_acte'])} : {round(taux * 100)} % réempruntent à la même période "
                   f"l'année suivante")
        pistes.append((-taux, -float(scores[siren]["proba"]), scores[siren], dec, e["lien"], [], e["genre"]))
    # 2. chantiers récents
    for siren, t in TRAVAUX.items():
        r = scores.get(siren)
        if not r or siren in exclus or recent(siren) or not eligible(r) or any(p[2]["siren"] == siren for p in pistes):
            continue
        t = sorted(t, key=lambda x: x["date"] or "", reverse=True)
        age = (jour_ref - date.fromisoformat(t[0]["date"][:10])).days
        if not une_fois(siren, age, 2, 25):
            continue
        objet = t[0]["objet"] if len(t[0]["objet"]) <= 80 else t[0]["objet"][:78] + "…"
        dec = (f"🏗 Chantier lancé le {fr_date(t[0]['date'])[:5]} : {objet}"
               + f" ({round(taux_obs['travaux_90j'] * 100)} % empruntent dans les 90 jours)")
        pistes.append((-taux_obs["travaux_90j"], -float(r["proba"]), r, dec, t[0].get("lien"), t[:1], "chantier"))
    pistes.sort(key=lambda p: (p[0], p[1]))
    global SURPLUS
    SURPLUS = pistes[n:]
    pistes = pistes[:n]
    # 3. modèle : les plus probables dans les 2 prochains mois (risque mensuel x probabilité annuelle), par roulement
    if len(pistes) < n:
        pris = {p[2]["siren"] for p in pistes}
        candidats = sorted((r for r in scores.values() if eligible(r) and r["siren"] not in exclus
                            and r["siren"] not in pris and not recent(r["siren"])),
                           key=lambda r: -float(r["proba"]))[:3 * VIVIER]
        vivier = sorted(candidats, key=lambda r: -proche(r))[:VIVIER]
        k = (jour_ref.toordinal() * n) % max(1, len(vivier))
        for r in (vivier[k:] + vivier[:k])[: n - len(pistes)]:
            dec = f"🧮 {r['facteurs'] or 'profil d emprunteur régulier'}"
            if r.get("dernier_marche_date"):
                dec += f" · dernier chantier le {fr_date(r['dernier_marche_date'])}"
            pistes.append((0, 0, r, dec, None, [], "modele"))
    noms = {v: k for k, v in CODES.items()}
    out = []
    for _, _, r, dec, lien, t, genre in pistes:
        proche(r)
        ent = {"type": r["type"], "siren": r["siren"], "code_insee": r.get("code_insee"), "nom": r["nom"],
               "population": r["population"], "dept": r["dept"], "departement": noms.get(r["dept"], "")}
        ent["contacts"] = veille.contacts(ent)
        emp = float(r["emprunts_derniere_annee"] or 0)
        fin = [f"emprunté {court(emp)} en {r['annee_comptes']}" if emp >= 20000 else f"aucun emprunt en {r['annee_comptes']}",
               f"investi {court(float(r['depense_equipement'] or 0))}"]
        if r.get("tresorerie") not in (None, ""):
            tj = f" ({r['tresorerie_jours']} j de dépenses)" if r.get("tresorerie_jours") not in (None, "") else ""
            fin.append(f"trésorerie {court(float(r['tresorerie']))}{tj}")
        out.append({"siren": r["siren"], "entite": ent, "prediction": r, "declencheur": dec, "genre": genre,
                    "finances": "📊 Comptes " + r["annee_comptes"] + " : " + ", ".join(fin), "lien": lien,
                    "facteurs": r.get("facteurs"), "travaux": t})
    return out


def bloc_lecture(couv, jours):
    def nb(cle, motif):
        import re
        v = " ".join(x for k, vals in couv.items() if cle in k for x in vals)
        return sum(int(x.replace(" ", "")) for x in re.findall(motif, v))
    actes = nb("Mégalis Bretagne", r"(\d+) actes publiés lus") + nb("RECIA", r"(\d+) actes publiés lus")
    articles = nb("Presse", r"(\d+) articles distincts")
    sites = nb("Sites des mairies", r"(\d+) sites lus")
    avis = nb("BOAMP", r"(\d+) avis encore ouverts") + nb("BOAMP", r"(\d+) avis publiés")
    morceaux = [f"{actes} actes", f"{articles} articles de presse", f"{sites} sites de mairies",
                f"{avis} avis BOAMP", "Mégalis, e-marchespublics, AWS, TED"]
    erreurs = [k for k, v in couv.items() if any("ERREUR" in x for x in v)]
    L = [f"🔎 Lu {periode(jours)} : " + " · ".join(morceaux) + ". Détail dans le Google Sheets."]
    if erreurs:
        L.append("⚠️ Source en panne : " + ", ".join(erreurs))
    return "\n".join(L)


def lignes_sheet(q, idx, jours, couv, calc=()):
    detect = datetime.now(PARIS).strftime("%d/%m/%Y")
    opp, ec = [], []
    for o in q.get("opportunites", []):
        e = fiche_de(o, idx)
        nom, fonction, tel, mail = interlocuteur(e)
        opp.append([detect, e.get("region", ""), e.get("departement", ""), CODES.get(e.get("departement"), ""),
                    e.get("type", ""), (e.get("contacts") or {}).get("nom_officiel") or e.get("nom", ""),
                    e.get("population", ""), e.get("annee_population", ""), o["siren"], nom, fonction, tel, mail,
                    o["nature"], o.get("montant") if o.get("montant") is not None else "", o["niveau"],
                    o.get("statut", ""), fr_date(o.get("date_publication")), fr_date(o.get("date_limite")),
                    o.get("source", ""), o["lien"], "Non", ""])
    deja = {x.get("lien") for x in q.get("ecartes", [])}
    for x in q.get("ecartes", []) + [x for x in ECARTS_AUTO if x["lien"] not in deja]:
        e = idx.get(x.get("siren"), {})
        dep = e.get("departement")
        ec.append([detect, x.get("nom") or e.get("nom", ""), x.get("siren", ""),
                   f"{dep} ({CODES.get(dep, '')})" if dep else "", x.get("acte", ""),
                   fr_date(x.get("date_publication")), x.get("motif", ""), x.get("lien", "")])
    ouvertes = sum(1 for o in q.get("opportunites", []) if o.get("niveau") == "A")
    regions = {}
    for o in q.get("opportunites", []):
        e = fiche_de(o, idx)
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
                "Pays de la Loire et Normandie : pas de plateforme publique des actes ; couverture par les sites "
                "des mairies, les appels d'offres, la presse locale et le modèle prédictif. Presse lue sur les "
                "titres et chapeaux (Google News, Bing News).",
                q.get("suivi", "")]]
    calcul = []
    for rang, c in enumerate(calc, 1):
        e, p = c["entite"], c["prediction"]
        nom, fonction, tel, mail = interlocuteur(e)
        t = (c.get("travaux") or [{}])[0]
        calcul.append([detect, rang, c["siren"], e.get("nom", ""), e.get("type", ""), e.get("departement", ""),
                       e.get("population", ""), p.get("proba", ""), p.get("proba_annee_suivante", ""),
                       c["declencheur"], fr_date(t.get("date")) if t.get("date") else "", c["finances"],
                       c.get("facteurs") or "", nom, fonction, tel, mail, c.get("lien") or "", "Non", ""])
    return {"Opportunités": opp, "Actes écartés": ec, "Journal de veille": journal, "Liste calculée": calcul}


ENTETES = {"Liste calculée": ["Date", "Rang", "SIREN", "Collectivité", "Type", "Département", "Population",
                              "Probabilité année en cours", "Probabilité année suivante", "Déclencheur",
                              "Date du chantier", "Comptes", "Facteurs du modèle", "Interlocuteur", "Fonction",
                              "Téléphone", "Courriel", "Lien", "Appelé", "Notes"]}


def main():
    qf, cfs, opts = args()
    q = json.load(open(qf))
    if "--webhook" in opts:
        # ce qui est déjà dans le Google Sheets n'est pas reproposé comme nouveau
        try:
            u = opts["--webhook"] + "?" + urllib.parse.urlencode({"secret": opts.get("--secret", "")})
            with urllib.request.urlopen(u, timeout=60) as r:
                vus = {x.get("lien"): x.get("date") for x in json.loads(r.read()).get("deja_signales", [])}
            for o in q.get("opportunites", []):
                if o.get("lien") in vus and o.get("niveau") in ("A", "B"):
                    o["niveau"], o["statut"] = "C", f"déjà signalé le {vus[o['lien']]}"
        except Exception:
            pass
    idx, jours, couv = fiches(cfs)
    jour_ref = date.fromisoformat(jours[-1]) if jours else datetime.now(PARIS).date()
    certains = {o["siren"] for o in q.get("opportunites", []) if o.get("niveau") in ("A", "B")}
    lundi = datetime.now(PARIS).weekday() == 0
    objectif = int(opts.get("--objectif", 10 if lundi else 7))
    mini = int(opts.get("--calcules", opts.get("--top", 5)))
    calc = [] if opts["--surs"] else liste_calculee(max(objectif - len(certains), mini),
                                                   {o["siren"] for o in q.get("opportunites", [])}, jour_ref)
    msg = message(q, idx, jours, calc, opts["--surs"]) + "\n" + bloc_lecture(couv, jours)
    if "--sortie" in opts:
        open(opts["--sortie"], "w").write(msg)
    print(msg)
    if "--webhook" in opts:
        body = json.dumps({"secret": opts.get("--secret", ""), "entetes": ENTETES,
                           "lignes": lignes_sheet(q, idx, jours, couv, calc)}).encode()
        req = urllib.request.Request(opts["--webhook"], data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            print("\nGoogle Sheets :", r.read().decode()[:500])


if __name__ == "__main__":
    main()
