"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { standardSchemaResolver as zodResolver } from "@hookform/resolvers/standard-schema";
import { z } from "zod";
import { Eye, EyeOff, LogIn, UserPlus, AlertCircle } from "lucide-react";

const loginSchema = z.object({
  email: z.string().email("Adresse e-mail invalide"),
  password: z.string().min(6, "Mot de passe requis (min. 6 caractères)"),
});

const registerSchema = z.object({
  nom: z.string().min(2, "Nom requis"),
  prenom: z.string().min(2, "Prénom requis"),
  email: z.string().email("Adresse e-mail invalide"),
  commune: z.string().optional(),
  password: z.string().min(8, "8 caractères minimum"),
  confirmPassword: z.string(),
  role_souhaite: z.enum(["entreprise", "referent", "elu"]),
}).refine(d => d.password === d.confirmPassword, {
  message: "Les mots de passe ne correspondent pas",
  path: ["confirmPassword"],
});

type LoginForm = z.infer<typeof loginSchema>;
type RegisterForm = z.infer<typeof registerSchema>;

const DEMO_USERS = [
  { email: "dgs@ca-airesuradour.fr", password: "demo1234", role: "admin", nom: "Martin", prenom: "Directeur" },
  { email: "agent@ca-airesuradour.fr", password: "demo1234", role: "agent", nom: "Dupont", prenom: "Chargé de mission" },
  { email: "elu@ca-airesuradour.fr", password: "demo1234", role: "elu", nom: "Bernard", prenom: "Élu" },
  { email: "commune@ca-airesuradour.fr", password: "demo1234", role: "referent", nom: "Lefebvre", prenom: "Référent" },
];

export default function ConnexionPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registerSuccess, setRegisterSuccess] = useState(false);

  const loginForm = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });
  const registerForm = useForm<RegisterForm>({ resolver: zodResolver(registerSchema) });

  const onLogin = async (data: LoginForm) => {
    setError(null);
    await new Promise(r => setTimeout(r, 600));
    const user = DEMO_USERS.find(u => u.email === data.email && u.password === data.password);
    if (!user) {
      setError("Identifiants incorrects. Essayez un des comptes de démonstration ci-dessous.");
      return;
    }
    const session = { ...user, token: "demo-" + Date.now(), loginAt: new Date().toISOString() };
    localStorage.setItem("session", JSON.stringify(session));
    if (user.role === "admin") router.push("/admin");
    else if (user.role === "agent") router.push("/dashboard");
    else if (user.role === "elu") router.push("/dashboard");
    else router.push("/salles");
  };

  const onRegister = async (data: RegisterForm) => {
    setError(null);
    await new Promise(r => setTimeout(r, 800));
    const pending = JSON.parse(localStorage.getItem("pending_users") || "[]");
    pending.push({ ...data, id: Date.now(), valide: false, created_at: new Date().toISOString() });
    localStorage.setItem("pending_users", JSON.stringify(pending));
    setRegisterSuccess(true);
  };

  if (registerSuccess) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center bg-paper px-4">
        <div className="max-w-md w-full bg-card rounded-2xl border border-ink/5 shadow-sm p-10 text-center">
          <div className="w-16 h-16 bg-moss/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <UserPlus size={32} className="text-moss" />
          </div>
          <h2 className="font-display font-bold text-pine text-2xl mb-3">Demande envoyée</h2>
          <p className="text-ink/60 font-body mb-6">
            Votre demande de compte a été transmise à l&apos;administrateur. Vous recevrez un e-mail de confirmation dès validation.
          </p>
          <button onClick={() => { setRegisterSuccess(false); setMode("login"); }} className="text-moss font-display font-semibold underline text-sm">
            Retour à la connexion
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] bg-paper flex items-center justify-center px-4 py-12">
      <div className="max-w-md w-full">
        {/* Logo */}
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex flex-col items-center">
            <div className="w-12 h-12 bg-pine rounded-full flex items-center justify-center text-gold font-display font-bold text-xl mb-3">A</div>
            <span className="font-display font-bold text-pine text-lg">CA Aire-sur-l&apos;Adour</span>
          </Link>
          <p className="text-ink/50 text-sm mt-2 font-body">Espace collaborateurs &amp; partenaires</p>
        </div>

        {/* Tabs */}
        <div className="bg-card rounded-2xl border border-ink/5 shadow-sm overflow-hidden">
          <div className="flex border-b border-ink/5">
            <button
              onClick={() => { setMode("login"); setError(null); }}
              className={`flex-1 py-3.5 text-sm font-display font-semibold transition-colors ${mode === "login" ? "bg-pine text-white" : "text-ink/50 hover:text-ink hover:bg-paper"}`}
              aria-selected={mode === "login"}
            >
              Connexion
            </button>
            <button
              onClick={() => { setMode("register"); setError(null); }}
              className={`flex-1 py-3.5 text-sm font-display font-semibold transition-colors ${mode === "register" ? "bg-pine text-white" : "text-ink/50 hover:text-ink hover:bg-paper"}`}
              aria-selected={mode === "register"}
            >
              Créer un compte
            </button>
          </div>

          <div className="p-8">
            {error && (
              <div role="alert" className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 mb-5 text-sm font-body">
                <AlertCircle size={18} className="flex-shrink-0 mt-0.5" />
                {error}
              </div>
            )}

            {mode === "login" ? (
              <form onSubmit={loginForm.handleSubmit(onLogin)} noValidate className="space-y-4">
                <div>
                  <label htmlFor="login-email" className="block text-sm font-display font-semibold text-ink mb-1">
                    Adresse e-mail
                  </label>
                  <input
                    id="login-email"
                    type="email"
                    autoComplete="username"
                    className="w-full border border-ink/20 rounded-lg px-4 py-3 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss"
                    placeholder="vous@exemple.fr"
                    {...loginForm.register("email")}
                  />
                  {loginForm.formState.errors.email && (
                    <p role="alert" className="text-red-500 text-xs mt-1">{loginForm.formState.errors.email.message}</p>
                  )}
                </div>

                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label htmlFor="login-pwd" className="text-sm font-display font-semibold text-ink">Mot de passe</label>
                  </div>
                  <div className="relative">
                    <input
                      id="login-pwd"
                      type={showPwd ? "text" : "password"}
                      autoComplete="current-password"
                      className="w-full border border-ink/20 rounded-lg px-4 py-3 pr-12 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss"
                      {...loginForm.register("password")}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPwd(!showPwd)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-ink/40 hover:text-ink transition-colors"
                      aria-label={showPwd ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                    >
                      {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                  {loginForm.formState.errors.password && (
                    <p role="alert" className="text-red-500 text-xs mt-1">{loginForm.formState.errors.password.message}</p>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={loginForm.formState.isSubmitting}
                  className="w-full bg-pine text-white font-display font-bold py-3 rounded-xl hover:bg-pine-2 transition-colors disabled:opacity-60 flex items-center justify-center gap-2 mt-2"
                >
                  <LogIn size={18} />
                  {loginForm.formState.isSubmitting ? "Connexion…" : "Se connecter"}
                </button>
              </form>
            ) : (
              <form onSubmit={registerForm.handleSubmit(onRegister)} noValidate className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label htmlFor="reg-prenom" className="block text-sm font-display font-semibold text-ink mb-1">Prénom *</label>
                    <input id="reg-prenom" type="text" className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss" {...registerForm.register("prenom")} />
                    {registerForm.formState.errors.prenom && <p role="alert" className="text-red-500 text-xs mt-1">{registerForm.formState.errors.prenom.message}</p>}
                  </div>
                  <div>
                    <label htmlFor="reg-nom" className="block text-sm font-display font-semibold text-ink mb-1">Nom *</label>
                    <input id="reg-nom" type="text" className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss" {...registerForm.register("nom")} />
                    {registerForm.formState.errors.nom && <p role="alert" className="text-red-500 text-xs mt-1">{registerForm.formState.errors.nom.message}</p>}
                  </div>
                </div>

                <div>
                  <label htmlFor="reg-email" className="block text-sm font-display font-semibold text-ink mb-1">E-mail *</label>
                  <input id="reg-email" type="email" className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss" {...registerForm.register("email")} />
                  {registerForm.formState.errors.email && <p role="alert" className="text-red-500 text-xs mt-1">{registerForm.formState.errors.email.message}</p>}
                </div>

                <div>
                  <label htmlFor="reg-role" className="block text-sm font-display font-semibold text-ink mb-1">Profil *</label>
                  <select id="reg-role" className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss bg-white" {...registerForm.register("role_souhaite")}>
                    <option value="entreprise">Entreprise / Porteur de projet</option>
                    <option value="referent">Référent de commune</option>
                    <option value="elu">Élu</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="reg-commune" className="block text-sm font-display font-semibold text-ink mb-1">Commune (optionnel)</label>
                  <input id="reg-commune" type="text" placeholder="Aire-sur-l'Adour, Grenade-sur-l'Adour…" className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss" {...registerForm.register("commune")} />
                </div>

                <div>
                  <label htmlFor="reg-pwd" className="block text-sm font-display font-semibold text-ink mb-1">Mot de passe *</label>
                  <div className="relative">
                    <input id="reg-pwd" type={showPwd ? "text" : "password"} className="w-full border border-ink/20 rounded-lg px-3 py-2.5 pr-10 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss" {...registerForm.register("password")} />
                    <button type="button" onClick={() => setShowPwd(!showPwd)} className="absolute right-3 top-1/2 -translate-y-1/2 text-ink/40" aria-label={showPwd ? "Masquer" : "Afficher"}>
                      {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  {registerForm.formState.errors.password && <p role="alert" className="text-red-500 text-xs mt-1">{registerForm.formState.errors.password.message}</p>}
                </div>

                <div>
                  <label htmlFor="reg-confirm" className="block text-sm font-display font-semibold text-ink mb-1">Confirmer le mot de passe *</label>
                  <input id="reg-confirm" type={showPwd ? "text" : "password"} className="w-full border border-ink/20 rounded-lg px-3 py-2.5 text-sm font-body focus:outline-none focus:ring-2 focus:ring-moss" {...registerForm.register("confirmPassword")} />
                  {registerForm.formState.errors.confirmPassword && <p role="alert" className="text-red-500 text-xs mt-1">{registerForm.formState.errors.confirmPassword.message}</p>}
                </div>

                <p className="text-xs text-ink/40 font-body bg-paper rounded-lg p-3">
                  Votre compte sera activé après validation par un administrateur. Vous recevrez un e-mail de confirmation.
                </p>

                <button
                  type="submit"
                  disabled={registerForm.formState.isSubmitting}
                  className="w-full bg-moss text-white font-display font-bold py-3 rounded-xl hover:bg-pine transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  <UserPlus size={18} />
                  {registerForm.formState.isSubmitting ? "Envoi…" : "Demander un compte"}
                </button>
              </form>
            )}
          </div>
        </div>

        {/* Demo accounts */}
        <div className="mt-6 bg-gold/10 border border-gold/30 rounded-xl p-4">
          <p className="text-xs font-display font-bold text-pine mb-3">Comptes de démonstration (maquette)</p>
          <div className="space-y-2">
            {DEMO_USERS.map(u => (
              <button
                key={u.email}
                onClick={() => {
                  loginForm.setValue("email", u.email);
                  loginForm.setValue("password", u.password);
                  setMode("login");
                }}
                className="w-full text-left flex items-center justify-between py-1.5 px-3 rounded-lg hover:bg-white/50 transition-colors"
              >
                <span className="text-xs text-ink/70 font-mono">{u.email}</span>
                <span className={`text-xs font-display font-bold px-2 py-0.5 rounded-full ${
                  u.role === "admin" ? "bg-pine text-white" :
                  u.role === "agent" ? "bg-moss text-white" :
                  u.role === "elu" ? "bg-gold text-pine" : "bg-ink/10 text-ink"
                }`}>{u.role}</span>
              </button>
            ))}
          </div>
          <p className="text-xs text-ink/40 mt-2 font-body">Mot de passe : demo1234 — Cliquer pour pré-remplir</p>
        </div>

        <p className="text-center text-xs text-ink/30 mt-4 font-body">
          <Link href="/" className="hover:text-ink transition-colors">← Retour à l&apos;accueil</Link>
        </p>
      </div>
    </div>
  );
}
