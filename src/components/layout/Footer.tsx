import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-pine text-white py-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div>
            <h3 className="font-display font-bold text-gold mb-3">CA Aire-sur-l&apos;Adour</h3>
            <p className="text-white/70 text-sm leading-relaxed">
              Communauté d&apos;Agglomération d&apos;Aire-sur-l&apos;Adour<br />
              22 communes — Axe A65 Bordeaux–Pau<br />
              Landes (40) &amp; Gers (32)
            </p>
          </div>
          <div>
            <h3 className="font-display font-semibold text-white/90 mb-3">Liens utiles</h3>
            <ul className="flex flex-col gap-2 text-sm text-white/70">
              <li><Link href="/mentions-legales" className="hover:text-gold transition-colors">Mentions légales</Link></li>
              <li><Link href="/politique-confidentialite" className="hover:text-gold transition-colors">Politique de confidentialité</Link></li>
              <li><Link href="/accessibilite" className="hover:text-gold transition-colors">Accessibilité</Link></li>
              <li><a href="mailto:contact@ca-airesuradour.fr" className="hover:text-gold transition-colors">Contact</a></li>
            </ul>
          </div>
          <div>
            <h3 className="font-display font-semibold text-white/90 mb-3">Avertissement</h3>
            <p className="text-white/70 text-sm leading-relaxed">
              Ce site est une{" "}
              <strong className="text-gold">maquette de démonstration</strong>{" "}
              sans caractère officiel. Les données présentées sont indicatives.
            </p>
          </div>
        </div>
        <div className="mt-8 pt-8 border-t border-white/10 text-center text-white/40 text-xs">
          © 2025 CA Aire-sur-l&apos;Adour — Maquette prototype —{" "}
          <a href="mailto:rgpd@ca-airesuradour.fr" className="hover:text-gold transition-colors">
            rgpd@ca-airesuradour.fr
          </a>
        </div>
      </div>
    </footer>
  );
}
