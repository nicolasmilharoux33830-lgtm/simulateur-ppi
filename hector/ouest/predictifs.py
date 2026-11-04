"""A prédictifs : collectivités qui n'ont encore rien écrit, mais dont un déclencheur daté ET les comptes
prouvent qu'elles vont devoir financer quelque chose dans les semaines qui viennent.

Un « A prédictif » n'est jamais mêlé aux A et B écrits : il est calculé, pas lu. Pour en être un, il faut :
1. un déclencheur fort et récent :
   - ligne de trésorerie arrivant à sa date anniversaire (-10 à +45 jours) ;
   - marchés de travaux attribués depuis 180 jours (DECP) dont le montant dépasse ce que la collectivité
     peut payer seule ;
   - subvention votée dont une part importante reste à percevoir et que la trésorerie ne peut pas avancer ;
2. un besoin chiffré à partir des comptes 2025 (OFGL, scores.csv) :
   besoin = travaux TTC - fonds de roulement disponible (au-delà de 30 jours de dépenses de fonctionnement)
            - une année d'épargne nette - subventions encore à percevoir ;
   ou, pour une ligne de trésorerie, une trésorerie tendue ou une ligne déjà renouvelée les années passées ;
3. une collectivité finançable : épargne nette positive et désendettement de 12 ans au plus ;
4. au moins deux signaux indépendants (le déclencheur + un autre : second déclencheur, trésorerie tendue,
   probabilité du modèle, signal écrit de la semaine, emprunt annuel habituel) ;
5. aucun emprunt ni ligne signé récemment (registre Mégalis / RECIA), pas déjà appelée, pas déjà proposée.

Les taux de départ sont ceux observés sur l'historique breton (imminence.TAUX) ; le score combine les signaux
en « ou » probabiliste. Il sert à classer, pas à promettre.

  (dans rapport.py) liste(n, exclus, jour, contexte)
  python3 predictifs.py AAAA-MM-JJ [N]      essai hors routine (sans contacts ni Google Sheets)
"""
import csv
import json
import math
import os
import re
import sys
import unicodedata
from datetime import date, timedelta

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

TAUX = {"ligne": 0.41, "emprunt": 0.22, "travaux_90j": 0.29}
try:
    import imminence
    TAUX.update(imminence.TAUX)
except Exception:          # imminence est facultatif (essai hors routine)
    imminence = None

PLANCHER_JOURS = 30           # trésorerie gardée de côté : 30 jours de dépenses de fonctionnement
DESEND_MAX = 12               # au-delà, collectivité fragile : pas un bon dossier de crédit
BESOIN_MIN = 50_000           # besoin minimal pour justifier un appel
BESOIN_MIN_RRF = 0.05         # et au moins 5 % des recettes de fonctionnement
SCORE_MIN = 0.55
PAR_DEPT = 2                  # au plus 2 A prédictifs par département et par jour
# marchés qui ne sont pas un investissement à financer d'un coup : accords-cadres et bons de commande (montant
# maximum sur plusieurs années, pas un engagement), entretien courant, reprises de concessions
HORS_INVEST = re.compile(r"accord.?cadre|bons? de commande|marche subsequent|entretien|maintenance|fauchage|"
                         r"elagage|debroussaill|nettoyage|balayage|concessions? funeraire|reprise de concession|"
                         r"location|fourniture")


def norm(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def fnum(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def court(x):
    x = float(x)
    if abs(x) >= 1e6:
        return f"{x / 1e6:,.2f} M€".replace(",", " ").replace(".", ",")
    if abs(x) >= 1e4:
        return f"{x / 1e3:,.0f} k€".replace(",", " ")
    return f"{x:,.0f} €".replace(",", " ")


def fr(iso):
    try:
        return date.fromisoformat(iso[:10]).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso or ""


def chiffres(r):
    """Comptes 2025 d'une ligne de scores.csv : recettes, dépenses, épargne, trésorerie, dette."""
    treso, fdr, en, eq = (fnum(r.get(k)) for k in ("tresorerie", "fonds_roulement", "epargne_nette", "depense_equipement"))
    ten, teb, eq_rrf = fnum(r.get("x_ten")), fnum(r.get("x_teb")), fnum(r.get("x_eq_rrf"))
    rrf = None
    if en is not None and ten and abs(ten) > 0.005:
        rrf = en / ten
    elif eq and eq_rrf and eq_rrf > 0.001:
        rrf = eq / eq_rrf
    if not rrf or rrf <= 0:
        return None
    eb = teb * rrf if teb is not None else None
    drf = rrf - eb if eb is not None else None
    desend = fnum(r.get("x_desend"))
    c = {"rrf": rrf, "eb": eb, "drf": drf, "en": en, "eq": eq, "treso": treso, "fdr": fdr, "desend": desend,
         "pop": int(fnum(r.get("population")) or 0), "annee": r.get("annee_comptes") or "2025",
         "emprunts": fnum(r.get("emprunts_derniere_annee")) or 0.0}
    if drf and drf > 0:
        c["treso_j"] = treso / drf * 365 if treso is not None else None
        c["plancher"] = drf * PLANCHER_JOURS / 365
        c["fdr_dispo"] = max(0.0, (fdr or 0.0) - c["plancher"])
    else:
        c["treso_j"], c["plancher"], c["fdr_dispo"] = None, 0.0, max(0.0, fdr or 0.0)
    return c


def financable(c):
    """Épargne nette positive et désendettement d'au plus 12 ans (dette nulle : finançable)."""
    if c["en"] is None or c["en"] <= 0 or c["eb"] is None or c["eb"] <= 0:
        return False, "épargne nette négative"
    if c["desend"] is not None and c["desend"] > DESEND_MAX:
        return False, f"désendettement {c['desend']:.0f} ans"
    return True, ""


def ligne_comptes(c):
    p = []
    if c.get("treso_j") is not None:
        p.append(f"trésorerie {court(c['treso'])} ({c['treso_j']:.0f} j de dépenses)")
    p.append(f"épargne nette {court(c['en'])}")
    if c["desend"] is not None:
        p.append("aucune dette" if c["desend"] < 0.05 else f"désendettement {c['desend']:.1f} ans".replace(".", ","))
    if c["emprunts"] >= 20000:
        p.append(f"emprunté {court(c['emprunts'])} en {c['annee']}")
    return f"📊 Comptes {c['annee']} : " + ", ".join(p) + " → finançable."


def signe_depuis(siren, depuis, registre, recents):
    """Emprunt ou ligne signé depuis la date `depuis` (registre Mégalis / RECIA, actes des 75 derniers jours)."""
    for a in (recents or {}).get(siren, []):
        if (a.get("date") or "") >= depuis:
            return f"acte du {fr(a['date'])} : {a.get('objet', '')[:60]}"
    e = (registre or {}).get("collectivites", {}).get(siren) or {}
    for x in e.get("emprunts", []):
        if (x.get("signe_le") or "") >= depuis:
            return f"prêt signé le {fr(x['signe_le'])} ({x.get('banque') or x.get('preteur') or 'banque'})"
    for x in e.get("actes", []):
        if x.get("genre") == "emprunt" and (x.get("date") or "") >= depuis:
            return f"délibération d'emprunt du {fr(x['date'])}"
    return None


def lignes_a_echeance(registre, jour, avant=10, apres=45):
    """Lignes de trésorerie du registre dont l'anniversaire tombe entre jour-avant et jour+apres."""
    out = {}
    for siren, e in (registre or {}).get("collectivites", {}).items():
        dates = sorted({x["date"] for x in e.get("actes", []) if x.get("genre") == "ligne" and x.get("date")})
        if not dates:
            continue
        d = date.fromisoformat(dates[-1])
        try:
            ech = d.replace(year=d.year + 1)
        except ValueError:
            ech = d + timedelta(days=365)
        if -avant <= (ech - jour).days <= apres:
            x = next(a for a in e["actes"] if a.get("genre") == "ligne" and a.get("date") == dates[-1])
            habitude = any(300 <= (d - date.fromisoformat(y)).days <= 430 for y in dates[:-1])
            out[siren] = {"dernier_acte": dates[-1], "attendu": ech.isoformat(), "banque": x.get("banque"),
                          "objet": x.get("objet"), "lien": x.get("lien"), "deja_renouvele_avant": habitude,
                          "plateforme": "registre des actes"}
    return out


def subventions_a_percevoir(subv, siren, jour):
    """Subventions récentes (année N-1 ou N) : reste à percevoir connu (Région), sinon montant voté."""
    out = []
    for x in (subv or {}).get("collectivites", {}).get(siren, []):
        if (x.get("annee") or 0) < jour.year - 1 or (x.get("montant") or 0) < 20000:
            continue
        reste = x.get("reste")
        out.append({**x, "a_percevoir": float(reste if reste is not None else x["montant"]),
                    "reste_connu": reste is not None})
    return out


def evalue(siren, r, jour, ctx):
    """Signaux et calcul de besoin d'une collectivité. Renvoie None si ce n'est pas un A prédictif."""
    c = chiffres(r)
    if not c:
        return None
    ok, pourquoi = financable(c)
    if not ok:
        return None
    signaux, besoins, liens = [], [], []
    deja = None
    # --- 1. ligne de trésorerie à échéance ---
    e = (ctx.get("echeances") or {}).get(siren)
    lr = ctx["lignes_reg"].get(siren)
    ech = e if e and e.get("genre") == "ligne" else lr
    if ech:
        ecart = (date.fromisoformat(ech["attendu"]) - jour).days
        if -10 <= ecart <= 45:
            tendu = c.get("treso_j") is not None and c["treso_j"] < 60
            habitude = bool(ech.get("deja_renouvele_avant"))
            abondant = c.get("treso_j") is not None and c["treso_j"] > 240
            if (tendu or habitude) and not abondant:
                # renouvellement imminent (dans les 3 semaines, ou date dépassée de peu) : appel à passer tout de suite
                p = (0.55 if (tendu and habitude) else 0.48) + (0.1 if ecart <= 21 else 0)
                banque = (lr or {}).get("banque") or ech.get("banque")
                txt = (f"🔁 Ligne de trésorerie du {fr(ech['dernier_acte'])}" + (f" chez {banque}" if banque else "")
                       + f" : renouvellement attendu vers le {fr(ech['attendu'])[:5]}")
                pourq = []
                if habitude:
                    pourq.append("déjà renouvelée l'an passé")
                if tendu:
                    pourq.append(f"trésorerie fin {c['annee']} de {c['treso_j']:.0f} jours seulement")
                txt += " (" + ", ".join(pourq) + ")."
                signaux.append({"cle": "ligne", "p": p, "texte": txt, "fort": True})
                besoins.append(("ligne", None, "renouvellement de la ligne de trésorerie"))
                liens.append(ech.get("lien"))
                deja = deja or signe_depuis(siren, (jour - timedelta(days=60)).isoformat(), None, ctx.get("recents"))
    # --- 2. travaux attribués (DECP) ---
    d = (ctx.get("decp") or {}).get("collectivites", {}).get(siren) or {}
    tv = [t for t in d.get("travaux", []) if not t.get("entretien") and t.get("date")
          and (jour - date.fromisoformat(t["date"][:10])).days <= 180 and not HORS_INVEST.search(norm(t.get("objet")))]
    montant_ht = sum(float(t.get("montant") or 0) for t in tv)
    sv = subventions_a_percevoir(ctx.get("subv"), siren, jour)
    a_percevoir = sum(x["a_percevoir"] for x in sv)
    if tv and montant_ht >= 80_000:
        recent = max(t["date"][:10] for t in tv)
        premier = min(t["date"][:10] for t in tv)
        ttc = montant_ht * 1.2
        besoin = ttc - c["fdr_dispo"] - max(c["en"], 0) - a_percevoir
        seuil = max(BESOIN_MIN, BESOIN_MIN_RRF * c["rrf"])
        if besoin >= seuil and (jour - date.fromisoformat(recent)).days <= 150:
            signe = signe_depuis(siren, (date.fromisoformat(premier) - timedelta(days=60)).isoformat(),
                                 ctx.get("registre"), ctx.get("recents"))
            if signe:
                deja = signe
            poids = besoin / max(c["rrf"] * 0.1, BESOIN_MIN)
            p = min(0.6, TAUX["travaux_90j"] * (1 + math.log2(1 + poids)) / 2 + 0.1)
            # gros emprunt l'année des comptes : il a pu préfinancer ce chantier -> on le dit, et on baisse le score
            prefi = c["emprunts"] >= 0.4 * ttc
            if c["emprunts"] >= ttc:
                return None
            if prefi:
                p -= 0.15
            # le besoin calculé est-il absorbable ? désendettement après emprunt (dette 2025 + besoin) / épargne brute
            apres = ((c["desend"] or 0) * c["eb"] + besoin) / c["eb"]
            if apres > 20:
                return None          # besoin surestimé (subventions inconnues) ou collectivité qui ne pourra pas emprunter
            if apres > 15:
                p -= 0.15
            gros = max(tv, key=lambda t: float(t.get("montant") or 0))
            obj = (gros.get("objet") or "").strip()
            obj = obj if len(obj) <= 70 else obj[:68] + "…"
            txt = (f"🏗 {len(tv)} marché{'s' if len(tv) > 1 else ''} de travaux attribué{'s' if len(tv) > 1 else ''} "
                   f"depuis le {fr(premier)[:5]} ({court(montant_ht)} HT), dont « {obj} » "
                   f"({court(float(gros.get('montant') or 0))}, {fr(gros['date'])[:5]}).")
            signaux.append({"cle": "travaux", "p": p, "texte": txt, "fort": True})
            calc = (f"🧮 Besoin ≈ {court(besoin)} : travaux {court(ttc)} TTC − fonds de roulement disponible "
                    f"{court(c['fdr_dispo'])} − épargne nette {court(max(c['en'], 0))}"
                    + (f" − subventions à percevoir {court(a_percevoir)}" if a_percevoir else "") + ".")
            if prefi:
                calc += (f" ⚠️ {court(c['emprunts'])} déjà empruntés en {c['annee']} : vérifier s'ils financent"
                         f" ce chantier.")
            if apres > 15:
                calc += (f" ⚠️ Emprunter tout ce besoin porterait le désendettement à {apres:.0f} ans : une partie est"
                         f" sans doute subventionnée.")
            besoins.append(("travaux", besoin, calc))
    # --- 3. subvention à préfinancer ---
    for x in sv:
        if not x["reste_connu"] or x["a_percevoir"] < 50_000:
            continue
        if c["treso"] is not None and c["treso"] - c["plancher"] < x["a_percevoir"]:
            p = 0.35
            txt = (f"💶 {x['dispositif']} {x['annee']} : {court(x['montant'])} votés pour « {str(x.get('projet', ''))[:60]} », "
                   f"{court(x['a_percevoir'])} encore à percevoir, plus que la trésorerie disponible : prêt relais probable.")
            signaux.append({"cle": "relais", "p": p, "texte": txt, "fort": True})
            besoins.append(("relais", x["a_percevoir"], f"🧮 Préfinancement ≈ {court(x['a_percevoir'])} en attendant le versement."))
            break
    # --- 4. demande écrite mais pas décidée (signal C : débat d'orientation, projet chiffré, emprunt envisagé),
    #        confirmée par les comptes : la collectivité ne pourra pas payer sans emprunter ---
    cw = (ctx.get("c_par_siren") or {}).get(siren)
    if cw:
        txt_c = f"{cw.get('nature') or ''} {cw.get('statut') or ''}"
        montant_c = fnum(cw.get("montant"))
        besoin_c = (montant_c - c["fdr_dispo"] - max(c["en"], 0)) if montant_c else None
        parle_emprunt = bool(re.search(r"emprunt|pret|financement bancaire|ligne de tresorerie", norm(txt_c)))
        tendu_c = (c.get("treso_j") is not None and c["treso_j"] < 60) or (fnum(r.get("x_gap")) or 0) > 0.1
        if (besoin_c and besoin_c >= max(BESOIN_MIN, BESOIN_MIN_RRF * c["rrf"])) or (parle_emprunt and tendu_c):
            signaux.append({"cle": "ecrit", "p": 0.5, "fort": True,
                            "texte": f"👀 Écrit, pas encore décidé : {(cw.get('nature') or cw.get('statut') or '').strip()[:150]}"})
            if besoin_c and besoin_c > 0:
                besoins.append(("ecrit", besoin_c, f"🧮 Besoin ≈ {court(besoin_c)} : projet {court(montant_c)} − fonds de "
                                                   f"roulement disponible {court(c['fdr_dispo'])} − épargne nette "
                                                   f"{court(max(c['en'], 0))}."))
            else:
                besoins.append(("ecrit", None, "projet annoncé, trésorerie insuffisante pour le payer seule"))
            if cw.get("lien"):
                liens.append(cw["lien"])
    if not any(s["fort"] for s in signaux):
        return None
    # --- signaux d'appui ---
    if e and e.get("genre") == "emprunt":
        ecart = (date.fromisoformat(e["attendu"]) - jour).days
        if -15 <= ecart <= 60:
            signaux.append({"cle": "emprunt_annuel", "p": TAUX["emprunt"], "fort": False,
                            "texte": f"📅 Emprunt du {fr(e['dernier_acte'])} : beaucoup réempruntent à la même période."})
    if cw and not any(s["cle"] == "ecrit" for s in signaux):
        signaux.append({"cle": "ecrit_appui", "p": 0.3, "fort": False,
                        "texte": f"👀 Signal écrit récent : {(cw.get('nature') or cw.get('statut') or 'projet en cours')[:150]}."})
    if not any(s["cle"] == "relais" for s in signaux) and sv:
        s0 = max(sv, key=lambda x: x["montant"])
        if s0["montant"] >= 50_000:
            signaux.append({"cle": "subvention", "p": 0.2, "fort": False,
                            "texte": f"💶 Subvention {s0['dispositif']} {s0['annee']} de {court(s0['montant'])} : "
                                     f"le reste du projet est à financer."})
    p_mod = max(fnum(r.get("proba")) or 0, fnum(r.get("proba_annee_suivante")) or 0)
    if p_mod >= 0.3:
        signaux.append({"cle": "modele", "p": min(0.4, p_mod * 0.6), "fort": False,
                        "texte": f"🔮 Profil d'emprunteur : {round(p_mod * 100)} % de probabilité d'emprunter dans l'année (modèle)."})
    tendue = c.get("treso_j") is not None and c["treso_j"] < 60
    if tendue and not any(s["cle"] == "ligne" for s in signaux):
        signaux.append({"cle": "tension", "p": 0.2, "fort": False,
                        "texte": f"⚠️ Trésorerie fin {c['annee']} de {c['treso_j']:.0f} jours de dépenses seulement."})
    if len(signaux) < 2:
        return None
    if deja:
        return None
    score = 1 - math.prod(1 - s["p"] for s in signaux)
    if score < SCORE_MIN:
        return None
    signaux.sort(key=lambda s: (not s["fort"], -s["p"]))
    besoin_max = max((b[1] for b in besoins if b[1]), default=None)
    produit = {"ligne": "ligne de trésorerie", "travaux": "emprunt d'investissement", "relais": "prêt relais",
               "ecrit": "emprunt d'investissement"}
    return {"siren": siren, "score": round(score, 3), "signaux": signaux, "besoins": besoins, "comptes": c,
            "besoin": besoin_max, "produit": " + ".join(dict.fromkeys(produit[b[0]] for b in besoins)),
            "lien": next((u for u in liens if u), None), "prediction": r}


def contexte(registre=None, decp=None, subv=None, echeances=None, recents=None, c_semaine=(), jour=None):
    c_par = {}
    for o in c_semaine or ():
        c_par.setdefault(o.get("siren"), o)
    return {"registre": registre, "decp": decp, "subv": subv, "echeances": echeances or {}, "recents": recents or {},
            "c_par_siren": c_par, "lignes_reg": lignes_a_echeance(registre, jour) if registre and jour else {}}


def lien_comptes(r):
    if r.get("type") == "Commune" and r.get("code_insee"):
        return ("https://data.ofgl.fr/explore/dataset/ofgl-base-communes-consolidee/table/?refine.com_code="
                f"{r['code_insee']}")
    return f"https://data.ofgl.fr/explore/dataset/ofgl-base-gfp-consolidee/table/?refine.epci_code={r['siren']}"


def liste(n, exclus, jour, ctx, scores_csv=None):
    """Les n meilleurs A prédictifs du jour (au plus PAR_DEPT par département), du plus sûr au moins sûr."""
    chemin = scores_csv or os.path.join(ICI, "scores.csv")
    if not os.path.exists(chemin) or n <= 0:
        return []
    out = []
    for r in csv.DictReader(open(chemin, encoding="utf-8"), delimiter=";"):
        if r["siren"] in exclus:
            continue
        if int(fnum(r.get("population")) or 0) >= (10000 if r["type"] == "Commune" else 20000):
            continue
        x = evalue(r["siren"], r, jour, ctx)
        if x:
            out.append(x)
    out.sort(key=lambda x: (-x["score"], -(x["besoin"] or 0)))
    choisis, par = [], {}
    for x in out:
        dep = x["prediction"]["dept"]
        if par.get(dep, 0) >= PAR_DEPT:
            continue
        par[dep] = par.get(dep, 0) + 1
        choisis.append(x)
        if len(choisis) >= n:
            break
    # pas que des chantiers : dès 3 A prédictifs, le meilleur renouvellement de ligne ou prêt relais prend la
    # dernière place (ce sont les besoins les plus proches dans le temps)
    if n >= 3 and choisis and all(x["signaux"][0]["cle"] == "travaux" for x in choisis):
        autre = next((x for x in out if x["signaux"][0]["cle"] != "travaux" and x not in choisis
                      and par.get(x["prediction"]["dept"], 0) < PAR_DEPT), None)
        if autre:
            choisis[-1] = autre
    for x in choisis:
        x["lien"] = x["lien"] or lien_comptes(x["prediction"])
    liste.vivier = len(out)
    return choisis


liste.vivier = 0


def nature(x):
    """Phrase courte pour le Google Sheets."""
    b = f", besoin ≈ {court(x['besoin'])}" if x.get("besoin") else ""
    return f"A prédictif ({x['produit']}{b}) : " + x["signaux"][0]["texte"]


if __name__ == "__main__":
    j = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    lire = lambda f: json.load(open(os.path.join(ICI, f))) if os.path.exists(os.path.join(ICI, f)) else None
    ctx = contexte(lire("registre.json"), lire("signaux_decp.json"), lire("subventions.json"), jour=j)
    for x in liste(n, set(), j, ctx):
        r = x["prediction"]
        print(f"{r['nom']} ({r['dept']}, {r['population']} hab.) score {x['score']} · {x['produit']}")
        for s in x["signaux"]:
            print("   ", s["texte"])
        for b in x["besoins"]:
            if b[1]:
                print("   ", b[2])
        print("   ", ligne_comptes(x["comptes"]))
    print("vivier :", liste.vivier)
