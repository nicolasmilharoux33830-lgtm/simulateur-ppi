import Card from "@/components/ui/Card";

export const metadata = {
  title: "Accessibilité — CA Aire-sur-l'Adour",
};

export default function Accessibilite() {
  return (
    <div className="py-16 px-4 max-w-4xl mx-auto">
      <div className="mb-8 p-4 bg-gold/10 border border-gold/30 rounded-xl text-sm text-pine font-display font-semibold">
        Maquette de démonstration — sans caractère officiel
      </div>
      <h1 className="font-display font-bold text-pine text-4xl mb-4">Déclaration d&apos;accessibilité</h1>
      <p className="text-ink/60 mb-10">Référentiel RGAA 4.1 — Établie le 21 juin 2025</p>

      <div className="space-y-8">
        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Statut de conformité</h2>
          <div className="inline-flex items-center gap-2 bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2 rounded-full text-sm font-display font-semibold mb-4">
            Non conforme (prototype)
          </div>
          <p className="text-sm text-ink/70 leading-relaxed">
            Ce site est une maquette de démonstration. Aucun audit d&apos;accessibilité complet 
            n&apos;a été conduit. En phase de production, un audit RGAA 4.1 complet sera réalisé 
            par un prestataire habilité.
          </p>
        </Card>

        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Contenus non accessibles</h2>
          <div className="space-y-3">
            {[
              { critere: "Cartes interactives (Leaflet)", derogation: "Dérogation charge disproportionnée — alternative textuelle fournie" },
              { critere: "Graphiques Recharts", derogation: "Les données sont disponibles en tableau" },
              { critere: "Export Excel (SheetJS)", derogation: "Fonctionnalité non accessible au lecteur d'écran — alternative par impression" },
              { critere: "Contenu multilingue", derogation: "Certains termes techniques en anglais sans attribut lang" },
            ].map(({ critere, derogation }) => (
              <div key={critere} className="flex items-start gap-3 text-sm border-l-2 border-amber-300 pl-3">
                <div>
                  <strong className="text-ink font-display">{critere}</strong>
                  <p className="text-ink/50 text-xs mt-0.5">{derogation}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Signaler un problème d&apos;accessibilité</h2>
          <p className="text-sm text-ink/70 mb-4">
            Si vous rencontrez une difficulté d&apos;accès à un contenu ou à une fonctionnalité, vous pouvez nous contacter :
          </p>
          <div className="space-y-2 text-sm">
            <p>E-mail : <a href="mailto:accessibilite@ca-airesuradour.fr" className="text-moss underline">accessibilite@ca-airesuradour.fr</a></p>
            <p>Téléphone : (fictif) 05 00 00 00 00</p>
          </div>
          <div className="mt-4 p-3 bg-paper rounded-lg text-xs text-ink/50">
            En cas de non-réponse dans un délai de 2 jours ouvrés, vous pouvez saisir le <a href="https://www.defenseurdesdroits.fr" target="_blank" rel="noopener noreferrer" className="text-moss underline">Défenseur des droits</a>.
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Plan d&apos;amélioration</h2>
          <div className="space-y-3">
            {[
              { action: "Audit RGAA 4.1 complet", echeance: "T4 2025", statut: "Planifié" },
              { action: "Alternatives textuelles pour toutes les images", echeance: "T3 2025", statut: "En cours" },
              { action: "Navigation clavier complète", echeance: "T3 2025", statut: "En cours" },
              { action: "Compatibilité lecteurs d'écran (NVDA, JAWS)", echeance: "T4 2025", statut: "Planifié" },
              { action: "Tests utilisateurs avec personnes en situation de handicap", echeance: "T1 2026", statut: "Planifié" },
            ].map(({ action, echeance, statut }) => (
              <div key={action} className="flex items-center justify-between text-sm border-b border-ink/5 pb-3 last:border-0 last:pb-0">
                <span className="text-ink/70">{action}</span>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-xs text-ink/40">{echeance}</span>
                  <span className={`text-xs font-display font-semibold px-2 py-0.5 rounded-full ${
                    statut === "En cours" ? "bg-moss/10 text-moss" : "bg-ink/10 text-ink/50"
                  }`}>{statut}</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
