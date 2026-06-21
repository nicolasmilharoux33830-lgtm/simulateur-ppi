"use client";
import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";

const navLinks = [
  { href: "/", label: "Accueil" },
  { href: "/#implantez-vous", label: "Implantez-vous" },
  { href: "/#entreprises", label: "Entreprises" },
  { href: "/finance", label: "Espace pro" },
];

export default function Header() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 bg-card/95 backdrop-blur border-b border-ink/10 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link href="/" className="font-display font-bold text-pine text-xl flex items-center gap-2">
            <span className="w-8 h-8 bg-pine rounded-full flex items-center justify-center text-gold text-sm font-bold">A</span>
            <span>CA Aire-sur-l&apos;Adour</span>
          </Link>
          <nav className="hidden md:flex items-center gap-6" aria-label="Navigation principale">
            {navLinks.map((link) => (
              <Link key={link.href} href={link.href} className="text-ink/70 hover:text-pine font-body text-sm font-medium transition-colors">{link.label}</Link>
            ))}
          </nav>
          <div className="hidden md:flex items-center gap-3">
            <Link href="/connexion" className="bg-moss text-white hover:bg-pine px-4 py-2 rounded-lg text-sm font-display font-semibold transition-colors">Connexion</Link>
          </div>
          <button className="md:hidden p-2 text-ink rounded-lg hover:bg-paper transition-colors" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="mobile-menu" aria-label={open ? "Fermer le menu" : "Ouvrir le menu"}>
            {open ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>
      {open && (
        <div id="mobile-menu" className="md:hidden border-t border-ink/10 bg-card">
          <nav className="flex flex-col py-4 px-4 gap-1" aria-label="Navigation mobile">
            {navLinks.map((link) => (
              <Link key={link.href} href={link.href} className="px-3 py-2 text-ink/70 hover:text-pine hover:bg-paper rounded-lg font-body text-sm font-medium transition-colors" onClick={() => setOpen(false)}>{link.label}</Link>
            ))}
            <div className="pt-3 border-t border-ink/10 mt-3">
              <Link href="/connexion" className="block text-center bg-moss text-white hover:bg-pine px-4 py-2 rounded-lg text-sm font-display font-semibold transition-colors" onClick={() => setOpen(false)}>Connexion</Link>
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}
