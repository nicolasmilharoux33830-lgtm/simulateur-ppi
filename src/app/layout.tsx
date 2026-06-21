import type { Metadata } from "next";
import { Space_Grotesk, IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import Header from "@/components/layout/Header";
import Footer from "@/components/layout/Footer";
import MaquetteBadge from "@/components/ui/MaquetteBadge";
import SkipToContent from "@/components/ui/SkipToContent";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
});

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-ibm-plex-sans",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ibm-plex-mono",
});

export const metadata: Metadata = {
  title: "CA Aire-sur-l'Adour — Territoire d'entreprises",
  description:
    "Maquette de démonstration — Plateforme d'attractivité économique de la Communauté d'Agglomération d'Aire-sur-l'Adour. Foncier, aides, implantation.",
  robots: "noindex, nofollow",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" className={`${spaceGrotesk.variable} ${ibmPlexSans.variable} ${ibmPlexMono.variable}`}>
      <body>
        <SkipToContent />
        <Header />
        <main id="main-content">{children}</main>
        <Footer />
        <MaquetteBadge />
      </body>
    </html>
  );
}
