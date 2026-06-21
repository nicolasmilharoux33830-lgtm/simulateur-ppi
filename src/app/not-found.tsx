import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center py-20 px-4">
      <div className="text-center">
        <div className="text-8xl font-display font-bold text-pine/10 mb-4">404</div>
        <h1 className="font-display font-bold text-pine text-3xl mb-3">Page introuvable</h1>
        <p className="text-ink/60 mb-8 max-w-sm">La page que vous cherchez n&apos;existe pas ou a été déplacée.</p>
        <Link href="/" className="bg-pine text-white hover:bg-pine-2 px-6 py-3 rounded-lg font-display font-semibold transition-colors">Retour à l&apos;accueil</Link>
      </div>
    </div>
  );
}
