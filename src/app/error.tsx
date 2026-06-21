"use client";
import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex items-center justify-center py-20 px-4">
      <div className="text-center max-w-md">
        <div className="w-16 h-16 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
          <span className="text-3xl">⚠️</span>
        </div>
        <h1 className="font-display font-bold text-pine text-2xl mb-3">Une erreur est survenue</h1>
        <p className="text-ink/60 mb-6">
          Une erreur inattendue s&apos;est produite. Veuillez réessayer ou contacter le support si le problème persiste.
        </p>
        {error.digest && (
          <p className="text-xs text-ink/30 font-mono mb-6">Référence : {error.digest}</p>
        )}
        <div className="flex gap-3 justify-center">
          <button
            onClick={reset}
            className="bg-pine text-white hover:bg-pine-2 px-5 py-2.5 rounded-lg font-display font-semibold transition-colors"
          >
            Réessayer
          </button>
          <a
            href="/"
            className="border border-ink/20 text-ink hover:bg-paper px-5 py-2.5 rounded-lg font-display font-semibold transition-colors"
          >
            Accueil
          </a>
        </div>
      </div>
    </div>
  );
}
