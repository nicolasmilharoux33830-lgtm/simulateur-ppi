# MODULE « CHASSEUR » — bot Veille emprunts Ouest

Zone : Pays de la Loire, Bretagne, Centre-Val de Loire et Normandie (20 départements).
Départements à balayer un par un : Loire-Atlantique (44), Maine-et-Loire (49), Mayenne (53), Sarthe (72), Vendée (85), Côtes-d'Armor (22), Finistère (29), Ille-et-Vilaine (35), Morbihan (56), Cher (18), Eure-et-Loir (28), Indre (36), Indre-et-Loire (37), Loir-et-Cher (41), Loiret (45), Calvados (14), Eure (27), Manche (50), Orne (61), Seine-Maritime (76).

Quand tu l'exécutes : APRÈS l'envoi du rapport habituel (messages « sûrs » et, le lundi, « PROBABLES »). Le rapport habituel part toujours à l'heure, sans attendre le Chasseur. Le Chasseur dispose de 35 minutes au plus et de 70 requêtes au plus par passage ; il s'arrête avant si la limite est atteinte.

## Règles qui priment sur tout le reste du module
- Aucune information inventée, aucun grade gonflé. Mieux vaut 0 qu'un lead douteux.
- Les définitions A, B et C de la consigne principale restent valables : un « A » écrit (document qui dit qu'on consulte des banques ou qu'on choisit sa banque) garde sa phrase recopiée, son lien et sa date.
- Un « A croisé » (section 4) est un A prouvé par DEUX sources indépendantes, sans contrat trouvé après ces pièces. Dans le message, il porte l'étiquette « 🎯 A croisé » et cite les deux sources avec leur lien ; il ne prétend jamais qu'une consultation de banques est écrite si ce n'est pas le cas.
- Un signal isolé mais solide (une seule source) est un « B+ » : il va au radar (section 6), pas dans le message « sûrs ».
- Interdits, comme pour toute la veille : se connecter à Facebook ou lire un groupe privé, utiliser un compte personnel ou un faux compte, contourner un mur de connexion ou une protection anti-robot (Pappers Politique, IntraMuros, Infolocale, Illiwap sont protégés : n'en lis que ce que les moteurs de recherche affichent), ignorer un robots.txt. Une page refusée est notée « refus du site », jamais contournée.
- Les seuils restent : communes de moins de 10 000 habitants, EPCI de moins de 20 000 habitants.

## 1. MÉTHODE DE RECHERCHE

A. Balayage systématique
- Chaque passage couvre TOUS les départements de la zone, un par un.
- Pour chaque département, lance au moins une requête de chaque famille de la section 3 (en alternant les familles d'un jour à l'autre si la limite de 70 requêtes l'impose, et note lesquelles manquent).
- Ne t'arrête pas à la première page de résultats : ouvre les pages 2 et 3 quand la première est prometteuse.
- Objectif : au moins 40 requêtes par passage. Si tu n'as pas 5 A au total sur la semaine, continue selon F.

B. Rebond : depuis chaque signal, même faible, remonte la chaîne
1. Ouvre la page « délibérations » ou « conseil municipal » de son site et lis les 3 derniers conseils.
2. Cherche son ROB/DOB le plus récent et son budget primitif 2026.
3. Cherche ses marchés des 12 derniers mois (DECP, BOAMP, profil acheteur).
4. Cherche ses subventions (DETR, DSIL, Fonds vert, département, région, Europe).
5. Regarde son intercommunalité et ses syndicats : un projet peut y être porté.
6. Regarde les communes voisines du même EPCI : les projets vont souvent par grappes.
7. Note le cabinet financier cité (Finance Active, Seldon, Klopfer, Ressources Consultants, Stratorial...) : ses clients font des consultations structurées.

C. Opérateurs de recherche
- Utilise "guillemets", site:, filetype:pdf, OR, et l'année. Exemple : site:mairie-xxx.fr filetype:pdf "emprunt" 2026.
- Varie les synonymes : emprunt, prêt, financement bancaire, concours bancaire, réalisation d'un emprunt, contrat de prêt, offre de financement, mobilisation des fonds, ligne de trésorerie, prêt relais, préfinancement.

D. Lecture des pièces
- Ouvre chaque PDF et lis-le en entier : tableaux de financement, annexes, état de la dette. Si le PDF est scanné, utilise l'OCR (/tmp/hv/venv/bin/python avec budgets_pdf.pages_texte). S'il reste illisible, note « PDF illisible, appel nécessaire ».
- Dans un ROB, va droit à : besoin de financement, recours à l'emprunt, PPI, encours par prêteur, part à taux variable, emprunts arrivant à échéance.

E. Calendrier : adapte la chasse au moment de l'année
- Octobre à décembre : emprunts de fin d'année, renouvellements de lignes de trésorerie, ROB de l'exercice suivant.
- Janvier à avril : ROB, budgets primitifs, compte 1641 inscrit.
- Mai à juillet : décisions modificatives et budgets supplémentaires, ajouts d'emprunt.
- Toute l'année : marchés de travaux, sinistres, fins de portage foncier.
- 2026-2027 est le début du mandat municipal : cherche « PPI du mandat », « plan pluriannuel d'investissement 2026-2032 », « programme de mandat ».

F. Si le rendement est faible (moins de 5 A sur la semaine)
1. Remonte à 18 mois pour les projets dont les travaux démarrent en 2027.
2. Ajoute les familles de signaux non encore testées (section 3).
3. Recontrôle tous les B et B+ du radar (section 6) pour voir si un 2e signal est apparu.
4. Indique combien de requêtes tu as lancées et lesquelles n'ont rien donné.

## 2. SOURCES SUPPLÉMENTAIRES

Données structurées (à interroger en priorité)
- Budgets primitifs en open data (data.gouv.fr, jeux « Budgets » des opérateurs de la zone : Mégalis Bretagne, GIP RECIA) : compte 1641 inscrit en recette.
- Marchés attribués (DECP) : fichier signaux_decp.json déjà calculé chaque nuit (travaux, maîtrise d'œuvre, financier) ; decp.info et data.gouv.fr « DECP consolidées » pour creuser. Filtre : SIRET de l'acheteur, CPV 45 (travaux), au moins 300 000 € HT.
- BOAMP (boamp.fr, API opendatasoft) : avis de marché et d'attribution.
- Autorisations d'urbanisme (Sitadel, liste des permis sur data.gouv.fr) : un permis de construire déposé par une commune ou un EPCI pour un bâtiment public annonce des travaux dans 6 à 18 mois.
- Fonds vert, liste des projets subventionnés (data.gouv.fr) : déjà dans subventions.json.
- Subventions versées par les régions et départements (jeux « Subventions » SCDL sur data.gouv.fr et portails open data régionaux).
- Kohesio (kohesio.ec.europa.eu) : projets cofinancés par l'Europe (FEDER, LEADER), avec bénéficiaire et budget.
- OFGL (data.ofgl.fr), comptes individuels DGFiP, balances comptables : épargne, encours, dépenses d'équipement, trésorerie.
- Banatic : population, compétences, syndicats d'appartenance.
- Géorisques, base GASPAR : arrêtés de catastrophe naturelle par commune.

Actes et décisions
- Sites des communes et EPCI (délibérations, procès-verbaux, décisions du maire ou du président, convocations).
- Pappers Politique (politique.pappers.fr) : seulement les pages que les moteurs de recherche indexent (le site refuse les outils automatiques).
- Mégalis Bretagne (data.megalis.bretagne.bzh) et GIP RECIA (publication-actes.fr) : actes télétransmis en open data (déjà lus chaque jour par le script ; utilise-les pour creuser une collectivité précise avec python3 veille.py --historique SIREN).
- Recueils des actes administratifs des préfectures : arrêtés DSEC, créations de communes nouvelles, arrêtés de mise en demeure budgétaire (à exclure).
- Préfectures : listes DETR/DSIL, procès-verbaux des commissions DETR.
- Commissions permanentes des départements et des régions : subventions votées aux communes, contrats de territoire.

Acteurs qui connaissent les projets avant tout le monde
- Établissements publics fonciers (EPF Bretagne, EPF des Pays de la Loire, EPF de Normandie, EPFL locaux) : conventions de portage avec garantie de rachat. Fin de portage = rachat à financer à date connue.
- Syndicats départementaux d'énergie : programmes de travaux communaux (éclairage, rénovation, réseaux) avec participation de la commune. Ouest : SDEF 29, SDE 35, SDE 22, Morbihan Énergies, SYDELA 44, SIEML 49, SyDEV 85, SDE 53, SDE 72, SDE 18, SDE 28, SDE 36, SDE 37, SIDELC 41, SDE 45, SDEC Énergie 14, SIEGE 27, SDEM 50, SDE 61, SDE 76.
- Agences techniques départementales (ATD, ingénieries départementales) : rapports d'activité et missions d'assistance aux communes.
- Agences de l'eau (Loire-Bretagne, Seine-Normandie) : aides aux stations d'épuration et aux réseaux, donc emprunts sur les budgets eau et assainissement.
- ANCT : conventions Petites villes de demain et ORT (maquettes financières), lauréats Villages d'avenir.
- CAF (conventions territoriales globales, crèches, centres de loisirs) et ARS (maisons de santé) : équipements qui s'empruntent.
- Chambres régionales des comptes (ccomptes.fr) : investissements prévus et dette. Sert aussi à écarter les collectivités fragiles.

Presse et communication locale
- Presse régionale : Ouest-France, Le Télégramme, Presse Océan, Courrier de l'Ouest, Le Maine Libre, La Nouvelle République, La République du Centre, L'Écho Républicain, Paris-Normandie, actu.fr.
- Hebdomadaires locaux et sites d'info locaux du département.
- Bulletins municipaux en PDF : « bulletin municipal » + « emprunt » OR « financement » + 2026.
- Pages officielles des mairies sur les réseaux sociaux : tu ne les lis jamais toi-même ; seuls comptent les fils que la mairie republie sur son site et ce que le script a déjà remonté (type « Facebook » dans candidats.json).
- Localtis (Banque des Territoires), Maire-info : actualité réglementaire et appels à projets.

## 3. FAMILLES DE SIGNAUX ET REQUÊTES ([dép.] = chaque département de la zone)

F1. Besoin d'emprunt annoncé
"rapport d'orientation budgétaire 2027" "recours à l'emprunt" [dép.]
"débat d'orientation budgétaire" "besoin de financement" 2027 [dép.]
"emprunt d'équilibre" commune [dép.] 2026
"plan pluriannuel d'investissement" 2026-2032 commune [dép.]

F2. Consultation bancaire en cours
"autorise le maire à consulter" emprunt 2026 [dép.]
"consultation des établissements bancaires" 2026 [dép.]
"lancer une consultation" "emprunt" [dép.] 2026
"offres de financement" "établissements bancaires" [mois] 2026

F3. Trésorerie et relais
"ligne de trésorerie" renouvellement 2026 commune [dép.]
"prêt relais" subventions OR FCTVA 2026 [dép.]
"préfinancement" subventions commune [dép.] 2026

F4. Travaux engagés
avis d'attribution travaux école OR "groupe scolaire" OR "salle polyvalente" OR gymnase commune [dép.] 2026
"maison de santé" OR "station d'épuration" OR "réseau d'assainissement" marché travaux [dép.] 2026
"maîtrise d'œuvre" commune [dép.] 2026 (signal B, travaux en 2027)

F5. Subventions obtenues
"DETR 2026" "opérations" [dép.] liste
"Fonds vert" commune [dép.] 2026 subvention
"contrat de territoire" OR "contrat de ruralité" [dép.] 2026 commune programmation

F6. Foncier
"convention opérationnelle" OR "convention de réalisation" EPF commune [dép.]
"rachat" "portage" EPF commune 2026 OR 2027

F7. Sinistres
"catastrophe naturelle" 2026 commune [dép.] travaux réparation
digue OR voirie "dégâts" crue 2026 commune [dép.] marché

F8. Refinancement
ROB "taux variable" OR "Euribor" commune [dép.] 2026
"renégociation" OR "remboursement anticipé" emprunt commune [dép.] 2026

F9. Conseil financier
"Finance Active" OR "Seldon" OR "Klopfer" OR "Ressources Consultants" ROB 2027 [dép.]
marché "assistance financière" OR "prospective financière" commune [dép.] 2026

F10. Leads fermés, à garder pour la veille concurrence (jamais dans le message « sûrs »)
"décide de contracter auprès de" 2026 [dép.]
"retient l'offre" emprunt 2026 [dép.]

## 4. CROISEMENTS QUI DONNENT DES A
Un lead passe en « A croisé » quand au moins DEUX sources indépendantes confirment le même besoin ET qu'aucun contrat n'a été trouvé après ces pièces (vérifie avec python3 veille.py --historique SIREN et sur le site de la collectivité). Croisements types :
- budget 2026 avec compte 1641 + marché de travaux notifié ;
- ROB/DOB qui annonce un emprunt + subvention attribuée au même projet ;
- permis de construire d'un bâtiment public + plan de financement voté ;
- fin de portage EPF dans les 12 mois + délibération de rachat ;
- catastrophe naturelle + marché de réparation lancé ;
- prêt relais en cours + subvention pas encore versée ;
- part de dette à taux variable élevée + projet d'investissement (refinancement + financement nouveau).

## 5. CONTRÔLE AVANT ENVOI
Avant chaque message, réponds pour chaque lead :
1. Ai-je lu la pièce en entier, et pas seulement un extrait ?
2. Ai-je deux sources indépendantes pour un A croisé ?
3. Ai-je cherché un contrat signé après la dernière pièce ?
4. La population est-elle dans les seuils ?
5. Ai-je écarté une collectivité fragile (désendettement au-delà de 12 ans, mise en demeure budgétaire) ?
Si une réponse est non, le lead descend d'un grade.

## 6. RADAR
- Les leads B+ sont enregistrés dans le Google Sheets (onglet Opportunités, niveau « B+ », « statut » = « radar, contrôle avant le JJ/MM » à 30 jours au plus).
- À chaque passage, relis la liste des B+ (réponse du Google Sheets : python3 -c avec urllib sur l'adresse /tmp/hv/sheet_url?secret=..., clé « deja_signales », niveau « B+ ») ; recontrôle ceux dont la date de contrôle arrive à échéance pour voir si un 2e signal est apparu.
- Un B+ qui reçoit un 2e signal indépendant devient A croisé. Un B+ sans nouveau signal après 60 jours est classé C.
- En fin de message, indique combien de B ont été promus en A depuis le dernier passage.

## 7. SORTIE DU CHASSEUR
1. Écris /tmp/hv/qualifies_chasseur.json (même format que qualifies.json) avec les A (écrits ou croisés), B et B+ trouvés ; pour un A croisé, « nature » commence par « 🎯 A croisé : » et cite les deux sources, « extrait » recopie la phrase de la source la plus forte, « lien » est le lien de cette source, et le lien de la seconde source figure dans « nature ».
2. Génère le message : python3 rapport.py /tmp/hv/qualifies_chasseur.json /tmp/hv/*/candidats.json --surs --sortie /tmp/hv/message_chasseur.txt --webhook "$(cat /tmp/hv/sheet_url)" --secret "$(cat /tmp/hv/sheet_secret)" --lecture-seule (sans --webhook si sheet_url est vide). Relis-le (section 5), puis relance la même commande sans --lecture-seule pour écrire dans le Google Sheets.
3. Si message_chasseur.txt contient au moins une collectivité, ajoute à la fin le bloc de fin de passage et envoie-le par Telegram comme le rapport habituel, en second message intitulé « 🎯 Chasseur ». S'il n'y en a aucune, envoie seulement le bloc de fin de passage, en quatre lignes.

Bloc de fin de passage, toujours :
- Nombre de requêtes lancées et de pièces lues.
- Départements couverts, et ceux non couverts avec la raison.
- Familles de signaux qui ont donné le plus de leads.
- Nouvelles sources découvertes pendant la recherche, à ajouter au module.
- B promus en A depuis le dernier passage.
