import Card from "@/components/ui/Card";

export const metadata = {
  title: "Mentions légales — CA Aire-sur-l'Adour",
};

export default function MentionsLegales() {
  return (
    <div className="py-16 px-4 max-w-4xl mx-auto">
      <div className="mb-8 p-4 bg-gold/10 border border-gold/30 rounded-xl text-sm text-pine font-display font-semibold">
        Maquette de démonstration — sans caractère officiel
      </div>
      <h1 className="font-display font-bold text-pine text-4xl mb-10">Mentions légales</h1>

      <div className="space-y-8">
        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Éditeur du site</h2>
          <div className="text-sm text-ink/70 space-y-2 leading-relaxed">
            <p><strong className="text-ink">Communauté d&apos;Agglomération d&apos;Aire-sur-l&apos;Adour</strong></p>
            <p>Hôtel de Ville — Place du Général de Gaulle<br />40800 Aire-sur-l&apos;Adour</p>
            <p>Téléphone : (fictif) 05 00 00 00 00</p>
            <p>E-mail : <a href="mailto:contact@ca-airesuradour.fr" className="text-moss underline">contact@ca-airesuradour.fr</a></p>
            <p>SIRET : (fictif — données de démonstration)</p>
            <p>Président : (nom fictif — maquette)</p>
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Hébergeur</h2>
          <div className="text-sm text-ink/70 space-y-2 leading-relaxed">
            <p><strong className="text-ink">Prototype :</strong> Vercel Inc., 340 Pine Street Suite 701, San Francisco, CA 94104, États-Unis</p>
            <p className="text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3 mt-3">
              En production, un hébergement en France ou dans l&apos;Union Européenne est recommandé pour les services publics conformément aux recommandations de la CNIL.
            </p>
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Délégué à la protection des données (DPO)</h2>
          <div className="text-sm text-ink/70 space-y-2">
            <p>La CA Aire-sur-l&apos;Adour a désigné un délégué à la protection des données conformément au RGPD.</p>
            <p>Contact DPO : <a href="mailto:rgpd@ca-airesuradour.fr" className="text-moss underline">rgpd@ca-airesuradour.fr</a></p>
            <p className="text-xs text-ink/40">Adresse fictive — maquette de démonstration</p>
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Propriété intellectuelle</h2>
          <p className="text-sm text-ink/70 leading-relaxed">
            Ce site est une maquette de démonstration. Toutes les données, noms, chiffres et 
            représentations sont fictifs ou indicatifs. Aucun contenu ne saurait être reproduit 
            sans autorisation préalable.
          </p>
        </Card>

        <Card className="p-6">
          <h2 className="font-display font-bold text-pine text-xl mb-4">Cookies</h2>
          <p className="text-sm text-ink/70 leading-relaxed">
            Ce prototype utilise le stockage local (<code className="font-mono text-xs bg-paper px-1 py-0.5 rounded">localStorage</code>) pour la sauvegarde des données de formulaires à titre démonstratif. 
            Aucun cookie de traçage n&apos;est déposé.
          </p>
        </Card>
      </div>
    </div>
  );
}
