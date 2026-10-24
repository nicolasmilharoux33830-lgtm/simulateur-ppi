// Webhook du Google Sheets « Veille emprunts des collectivités (Hector) ».
// Installation (2 minutes) : dans le classeur, Extensions > Apps Script, coller ce code à la place du
// contenu, remplacer SECRET, puis Déployer > Nouveau déploiement > Application Web
// (Exécuter en tant que : moi ; Accès : tout le monde) et envoyer l'URL /exec à Hector.
//
// Hector y envoie chaque matin les nouvelles lignes ; il n'efface ni ne modifie jamais les lignes
// existantes. doGet renvoie ce qui a déjà été signalé (pas de doublon d'un jour à l'autre) et les
// collectivités déjà appelées (« Appelé » à Oui ou « Résultat de l'appel » rempli) : elles ne sont
// plus jamais reproposées.
const SECRET = 'REMPLACER_PAR_LE_SECRET';
const CLASSEUR = '';                  // vide si le script est créé depuis le classeur (Extensions > Apps Script)
const CLES = {                        // colonnes servant à repérer un doublon (1 = colonne A)
  'Opportunités': [9, 21],            // SIREN + lien source
  'Actes écartés': [3, 8],            // SIREN + lien
  'Journal de veille': [1, 2],        // date + période couverte
  'Liste calculée': [1, 3],           // date + SIREN
  'Probables': [1, 3],                // date + SIREN
  'Mesure par source': [1, 2],        // date + source
};
const TEXTE = { 'Opportunités': [4, 8, 9, 12], 'Actes écartés': [3], 'Probables': [3, 14] };
const APPEL = "Résultat de l'appel";

function classeur() {
  return CLASSEUR ? SpreadsheetApp.openById(CLASSEUR) : SpreadsheetApp.getActiveSpreadsheet();
}

// Colonne « Résultat de l'appel » juste après « Appelé » (ajoutée une fois, sans toucher aux données)
function colonneAppel(sh) {
  const tete = sh.getRange(1, 1, 1, sh.getLastColumn()).getDisplayValues()[0];
  if (tete.indexOf(APPEL) >= 0) return;
  const appele = tete.indexOf('Appelé');
  if (appele < 0) return;
  sh.insertColumnAfter(appele + 1);
  sh.getRange(1, appele + 2).setValue(APPEL).setFontWeight('bold');
}

function doPost(e) {
  const body = JSON.parse(e.postData.contents);
  if (body.secret !== SECRET) return reponse({ ok: false, erreur: 'secret' });
  const ss = classeur();
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
    if (onglet === 'Opportunités') colonneAppel(sh);
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
  const ss = classeur();
  const vus = [], appeles = new Set(), cRecents = [];
  const limite = new Date(Date.now() - 10 * 24 * 3600 * 1000);
  ['Opportunités', 'Probables'].forEach(function (onglet) {
    const sh = ss.getSheetByName(onglet);
    if (!sh || sh.getLastRow() < 2) return;
    const data = sh.getRange(1, 1, sh.getLastRow(), sh.getLastColumn()).getDisplayValues();
    const tete = data.shift();
    const iSiren = tete.indexOf('SIREN'), iAppele = tete.indexOf('Appelé'), iRes = tete.indexOf(APPEL);
    data.forEach(function (r) {
      const siren = String(r[iSiren]).trim();
      if (!siren) return;
      const fait = (iAppele >= 0 && /^oui/i.test(String(r[iAppele]).trim())) ||
                   (iRes >= 0 && String(r[iRes]).trim() !== '');
      if (fait) appeles.add(siren);
      if (onglet === 'Opportunités') {
        vus.push({ date: r[0], siren: siren, niveau: r[15], lien: r[20] });
        const d = lireDate(r[0]);
        if (r[15] === 'C' && d && d >= limite) cRecents.push({ siren: siren, niveau: 'C', nature: r[13], statut: r[16] });
      }
    });
  });
  return reponse({ ok: true, deja_signales: vus, deja_appeles: Array.from(appeles), c_recents: cRecents });
}

function lireDate(s) {               // « 24/10/2026 » ou « 2026-10-24 »
  const t = String(s).trim();
  let m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
  m = t.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : null;
}

function reponse(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
