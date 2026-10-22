import xml.etree.ElementTree as ET
NS = {"t": "http://www.minefi.gouv.fr/cp/demat/docbudgetaire"}
NATDEC = {"01": "Budget primitif", "02": "Décision modificative", "03": "Budget supplémentaire", "09": "Compte administratif"}

def val(el, tag):
    x = el.find(f"t:{tag}", NS)
    return x.get("V") if x is not None else None

def emprunts(xml_bytes):
    """Nouveaux emprunts votés (recettes réelles chapitre 16 hors 165/166/1688) dans ce document."""
    root = ET.fromstring(xml_bytes)
    out = {"natdec": None, "numdec": None, "exer": None, "dtedec": None, "lignes": [], "total_vote": 0.0, "total_budget": 0.0}
    for b in root.findall(".//t:Budget", NS):
        bb = b.find("t:BlocBudget", NS)
        if bb is not None:
            out["natdec"] = NATDEC.get(val(bb, "NatDec"), val(bb, "NatDec"))
            out["numdec"], out["exer"], out["dtedec"] = val(bb, "NumDec"), val(bb, "Exer"), val(bb, "DteDec")
        for lb in b.findall("t:LigneBudget", NS):
            nat, rd, op = val(lb, "Nature") or "", val(lb, "CodRD"), val(lb, "OpBudg")
            if rd == "R" and op == "0" and nat.startswith("16") and not nat.startswith(("165", "166", "1688")):
                prev = float(val(lb, "MtPrev") or 0)
                sup = lb.find("t:MtSup[@Code='BudgetHorsRAR']", NS)
                tot = float(sup.get("V")) if sup is not None else prev
                out["lignes"].append({"compte": nat, "vote_dans_acte": prev, "budget_total": tot})
                out["total_vote"] += prev
                out["total_budget"] += tot
    return out
