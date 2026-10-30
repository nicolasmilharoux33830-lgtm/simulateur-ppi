// Relais serveur vers les API publiques (OFGL pour les comptes, geo.api.gouv.fr pour la geolocalisation).
// Appele en meme origine depuis /crm.html et /communes.html : supprime tout probleme de CORS cote navigateur.
const OFGL =
  "https://data.ofgl.fr/api/explore/v2.1/catalog/datasets/ofgl-base-communes";
const GEO = "https://geo.api.gouv.fr/communes";

module.exports = async (req, res) => {
  try {
    const q = req.query || {};
    let target;
    if (q.mode === "geo") {
      const term = String(q.q || "").trim();
      if (!term) { res.status(400).json({ error: "parametre q requis" }); return; }
      target = GEO + "?nom=" + encodeURIComponent(term) +
        "&fields=nom,code,codeDepartement,siren,population,centre&boost=population&limit=15&format=json";
    } else if (q.mode === "search") {
      const term = String(q.q || "").replace(/"/g, "").trim();
      if (!term) { res.status(400).json({ error: "parametre q requis" }); return; }
      const where = encodeURIComponent('search(com_name,"' + term + '")');
      target = OFGL + "/records?where=" + where +
        "&select=siren,com_name,dep_name,ptot&limit=100";
    } else {
      const siren = String(q.siren || "").replace(/\D/g, "");
      if (siren.length !== 9) { res.status(400).json({ error: "siren invalide" }); return; }
      const sel = encodeURIComponent(
        "exer,agregat,montant,type_de_budget,lbudg,ptot,com_name,dep_name,dep_code,epci_name"
      );
      target = OFGL + "/exports/json?where=siren%3D%22" + siren + "%22&select=" + sel;
    }
    const r = await fetch(target);
    const body = await r.text();
    res.setHeader("content-type", "application/json; charset=utf-8");
    res.setHeader("cache-control", "public, max-age=3600");
    res.status(r.status).send(body);
  } catch (e) {
    res.status(502).json({ error: "source injoignable" });
  }
};
