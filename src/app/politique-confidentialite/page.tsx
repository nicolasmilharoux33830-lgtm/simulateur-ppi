import Card from "@/components/ui/Card";

export const metadata = {
  title: "Politique de confidentialité — CA Aire-sur-l'Adour",
};

const traitements = [
  {
    nom: "Gestion des leads d'implantation",
    finalite: "Traiter les demandes d'information et d'implantation d'entreprises",
    base: "Intérêt légitime",
    conservation: "3 ans à compter du dernier contact",
    destinataires: "Service développement économique de la CA",
  },
  {
    nom: "Réservation de salles",
    finalite: "Gérer les demandes de réservation d'espaces communautaires",
    base: "Exécution d'un contrat",
    conservation: "2 ans après la réservation",
    destinataires: "Service patrimoine et services techniques",
  },
  {
    nom: "Comptes utilisateurs (agents/élus)",
    finalite: "Authentification et accès aux outils professionnels",
    base: "Obligation légale / intérêt légitime",
    conservation: "Durée du mandat ou de la mission + 1 an",
    destinataires: "Service informatique et DPO",
  },
];

export default function PolitiqueConfidentialite() {
  return (
    <div className="py-16 px-4 max-w-4xl mx-auto">
      <div className="mb-8 p-4 bg-gold/10 border border-gold/30 rounded-xl text-sm text-pine font-display font-semibold">
        Maquette de démonstration — sans caractère officiel
      </div>
      <h1 className="font-display font-bold text-pine text-4xl mb-4">Politique de confidentialité</h1>
      <p className="text-ink/60 mb-10">Dernière mise à jour : 21 juin 2025</p>

      <div className="space-y-8">
        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Responsable du traitement</h2>
          <p className="text-sm text-ink/70">
            Communauté d&apos;Agglomération d&apos;Aire-sur-l&apos;Adour — contact : <a href="mailto:rgpd@ca-airesuradour.fr" className="text-moss underline">rgpd@ca-airesuradour.fr</a>
          </p>
        </Card>

        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-6">Traitements de données</h2>
          <div className="space-y-6">
            {traitements.map((t) => (
              <div key={t.nom} className="border border-ink/10 rounded-xl p-4">
                <h3 className="font-display font-semibold text-pine mb-3">{t.nom}</h3>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <div>
                    <dt className="text-xs font-display font-semibold text-ink/40 uppercase tracking-wide mb-1">Finalité</dt>
                    <dd className="text-ink/70">{t.finalite}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-display font-semibold text-ink/40 uppercase tracking-wide mb-1">Base légale</dt>
                    <dd className="text-moss font-semibold">{t.base}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-display font-semibold text-ink/40 uppercase tracking-wide mb-1">Conservation</dt>
                    <dd className="text-ink/70">{t.conservation}</dd>
                  </div>
                  <div>
                    <dt className="text-xs font-display font-semibold text-ink/40 uppercase tracking-wide mb-1">Destinataires</dt>
                    <dd className="text-ink/70">{t.destinataires}</dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Vos droits</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm text-ink/70">
            {[
              { droit: "Droit d'accès", desc: "Obtenir une copie de vos données personnelles" },
              { droit: "Droit de rectification", desc: "Corriger des données inexactes" },
              { droit: "Droit à l'effacement", desc: "Demander la suppression de vos données" },
              { droit: "Droit à la portabilité", desc: "Recevoir vos données dans un format structuré" },
              { droit: "Droit d'opposition", desc: "Vous opposer à un traitement basé sur l'intérêt légitime" },
              { droit: "Droit de limitation", desc: "Limiter temporairement un traitement" },
            ].map(({ droit, desc }) => (
              <div key={droit} className="flex items-start gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-moss mt-1.5 flex-shrink-0" />
                <div>
                  <strong className="text-ink font-display">{droit}</strong>
                  <p className="text-xs mt-0.5">{desc}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-6 p-4 bg-paper rounded-xl text-sm text-ink/70">
            Pour exercer vos droits : <a href="mailto:rgpd@ca-airesuradour.fr" className="text-moss underline font-semibold">rgpd@ca-airesuradour.fr</a>.
            En cas de litige, vous pouvez saisir la <a href="https://www.cnil.fr" target="_blank" rel="noopener noreferrer" className="text-moss underline">CNIL</a>.
          </div>
        </Card>
      </div>
    </div>
  );
}
