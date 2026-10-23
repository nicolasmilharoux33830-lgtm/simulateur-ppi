// Webhook du Google Sheets « Veille emprunts des collectivités (Hector) » : projet Apps Script
// autonome, puis Déployer > Nouveau déploiement > Application Web (Exécuter en tant que : moi ;
// Accès : tout le monde). Hector y envoie chaque matin les nouvelles lignes ; il n'efface ni ne
// modifie jamais les lignes existantes. doGet renvoie ce qui a déjà été signalé (pas de doublon
// d'un jour à l'autre).
const SECRET = 'REMPLACER_PAR_LE_SECRET';
const CLASSEUR = 'REMPLACER_PAR_ID_DU_CLASSEUR';
const CLES = {                        // colonnes servant à repérer un doublon (1 = colonne A)
  'Opportunités': [9, 21],            // SIREN + lien source
  'Actes écartés': [3, 8],            // SIREN + lien
  'Journal de veille': [1, 2],        // date + période couverte
  'Liste calculée': [1, 3],           // date + SIREN
};
const TEXTE = { 'Opportunités': [4, 8, 9, 12], 'Actes écartés': [3] };

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  if (body.secret !== SECRET) return reponse({ ok: false, erreur: 'secret' });
  const ss = SpreadsheetApp.openById(CLASSEUR);
  const bilan = {};
  Object.keys(body.lignes || {}).forEach(function (onglet) {
    let sh = ss.getSheetByName(onglet);
    const lignes = body.lignes[onglet] || [];
    if (!lignes.length) return;
    if (!sh) {
      sh = ss.insertSheet(onglet);
      const tete = (body.entetes || {})[onglet];
      if (tete) sh.getRange(1, 1, 1, tete.length).setValues([tete]).setFontWeight('bold');
      sh.setFrozenRows(1);
    }
    const cles = CLES[onglet] || [];
    const deja = new Set();
    const fin = sh.getLastRow();
    if (fin > 1 && cles.length) {
      const data = sh.getRange(2, 1, fin - 1, sh.getLastColumn()).getDisplayValues();
      data.forEach(function (r) { deja.add(cles.map(function (c) { return String(r[c - 1]).trim(); }).join('|')); });
    }
    const nouvelles = lignes.filter(function (r) {
      const k = cles.map(function (c) { return String(r[c - 1] == null ? '' : r[c - 1]).trim(); }).join('|');
      if (deja.has(k)) return false;
      deja.add(k);
      return true;
    });
    if (nouvelles.length) {
      const debut = sh.getLastRow() + 1;
      (TEXTE[onglet] || []).forEach(function (c) {
        sh.getRange(debut, c, nouvelles.length, 1).setNumberFormat('@');
      });
      sh.getRange(debut, 1, nouvelles.length, nouvelles[0].length).setValues(nouvelles);
    }
    bilan[onglet] = { recues: lignes.length, ajoutees: nouvelles.length };
  });
  return reponse({ ok: true, bilan: bilan });
}

function doGet(e) {
  if ((e.parameter || {}).secret !== SECRET) return reponse({ ok: false, erreur: 'secret' });
  const sh = SpreadsheetApp.openById(CLASSEUR).getSheetByName('Opportunités');
  const fin = sh ? sh.getLastRow() : 0;
  const vus = fin > 1 ? sh.getRange(2, 1, fin - 1, 21).getDisplayValues().map(function (r) {
    return { date: r[0], siren: r[8], niveau: r[15], lien: r[20] };
  }) : [];
  return reponse({ ok: true, deja_signales: vus });
}

function reponse(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
