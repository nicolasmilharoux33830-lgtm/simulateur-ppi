/* ============================================================
   COMMUNE DE LUGOS — JS Premium v2
   ============================================================ */

/* --- Loader --- */
window.addEventListener('load', () => {
  setTimeout(() => {
    document.getElementById('loader')?.classList.add('hidden');
  }, 2200);
});

document.addEventListener('DOMContentLoaded', () => {

  /* --- Navbar scroll --- */
  const navbar = document.getElementById('navbar');
  const onScroll = () => navbar?.classList.toggle('scrolled', window.scrollY > 60);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* --- Hamburger --- */
  const ham = document.querySelector('.hamburger');
  const mob = document.getElementById('mobile-menu');
  ham?.addEventListener('click', () => {
    ham.classList.toggle('open');
    mob?.classList.toggle('open');
    document.body.style.overflow = mob?.classList.contains('open') ? 'hidden' : '';
  });
  mob?.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
    ham?.classList.remove('open');
    mob?.classList.remove('open');
    document.body.style.overflow = '';
  }));

  /* --- Scroll reveal --- */
  const revealEls = document.querySelectorAll('[data-reveal]');
  const revealIO = new IntersectionObserver((entries) => {
    entries.forEach((e, i) => {
      if (e.isIntersecting) {
        const delay = e.target.dataset.delay || i * 80;
        setTimeout(() => e.target.classList.add('revealed'), delay);
        revealIO.unobserve(e.target);
      }
    });
  }, { threshold: 0.12 });
  revealEls.forEach(el => revealIO.observe(el));

  /* --- Counter animation --- */
  const counters = document.querySelectorAll('[data-count]');
  const counterIO = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (e.isIntersecting) {
        animateCount(e.target);
        counterIO.unobserve(e.target);
      }
    });
  }, { threshold: 0.5 });
  counters.forEach(c => counterIO.observe(c));

  function animateCount(el) {
    const target   = parseFloat(el.dataset.count);
    const suffix   = el.dataset.suffix || '';
    const prefix   = el.dataset.prefix || '';
    const decimals = (target % 1 !== 0) ? 1 : 0;
    const duration = 2000;
    const start    = performance.now();
    const step = (now) => {
      const p = Math.min((now - start) / duration, 1);
      const e = 1 - Math.pow(1 - p, 4);
      const v = e * target;
      el.textContent = prefix + (decimals ? v.toFixed(1) : Math.floor(v).toLocaleString('fr-FR')) + suffix;
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  /* --- Parallax hero --- */
  const heroBg = document.querySelector('.hero-bg');
  if (heroBg) {
    window.addEventListener('scroll', () => {
      const y = window.scrollY;
      heroBg.style.transform = `translateY(${y * 0.35}px)`;
    }, { passive: true });
  }

  /* --- Smooth scroll --- */
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      const id = a.getAttribute('href').slice(1);
      const el = document.getElementById(id);
      if (el) { e.preventDefault(); el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    });
  });

  /* --- Newsletter form --- */
  const nlForm = document.getElementById('nl-form');
  if (nlForm) {
    nlForm.addEventListener('submit', e => {
      e.preventDefault();
      const btn = nlForm.querySelector('button');
      const inp = nlForm.querySelector('input');
      btn.textContent = '✓ Inscrit(e) !';
      btn.disabled = true;
      inp.value = '';
      setTimeout(() => { btn.textContent = "S'inscrire"; btn.disabled = false; }, 4000);
    });
  }

  /* --- Contact form --- */
  const ctForm = document.getElementById('ct-form');
  if (ctForm) {
    ctForm.addEventListener('submit', e => {
      e.preventDefault();
      const btn = ctForm.querySelector('button[type="submit"]');
      btn.textContent = '✓ Message envoyé !';
      btn.disabled = true;
      ctForm.reset();
      setTimeout(() => { btn.textContent = 'Envoyer le message'; btn.disabled = false; }, 5000);
    });
  }

  /* ============================================================
     SYSTÈME DE CONNEXION
     ============================================================ */
  const USERS = {
    'maire@lugos.fr':   { password: 'Lugos2026!', name: 'E. Tostain', role: 'Mairie' },
    'citoyen@lugos.fr': { password: 'Lugos33830', name: 'Mon espace',  role: 'Citoyen' },
  };

  const overlay   = document.getElementById('login-overlay');
  const loginForm = document.getElementById('login-form');
  const loginError= document.getElementById('login-error');
  const navLogin  = document.getElementById('nav-login');
  const navUser   = document.getElementById('nav-user');
  const navUserName = document.getElementById('nav-user-name');

  /* Check session */
  const session = JSON.parse(localStorage.getItem('lugos_session') || 'null');
  if (session) setLoggedIn(session);

  /* Open modal */
  document.querySelectorAll('[data-open-login]').forEach(btn => {
    btn.addEventListener('click', (e) => { e.preventDefault(); openLogin(); });
  });

  /* Close modal */
  document.getElementById('close-login')?.addEventListener('click', closeLogin);
  overlay?.addEventListener('click', e => { if (e.target === overlay) closeLogin(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLogin(); });

  /* Tabs */
  const tabs = document.querySelectorAll('.lm-tab');
  tabs.forEach(t => t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    const tab = t.dataset.tab;
    document.querySelectorAll('.lm-panel').forEach(p => p.style.display = p.id === tab ? 'flex' : 'none');
  }));

  /* Submit login */
  loginForm?.addEventListener('submit', e => {
    e.preventDefault();
    const email = loginForm.querySelector('#login-email')?.value.trim().toLowerCase();
    const pass  = loginForm.querySelector('#login-pass')?.value;
    const user  = USERS[email];
    if (user && user.password === pass) {
      const sess = { email, name: user.name, role: user.role };
      localStorage.setItem('lugos_session', JSON.stringify(sess));
      setLoggedIn(sess);
      closeLogin();
      showToast(`Bienvenue, ${user.name} !`);
    } else {
      loginError.classList.add('show');
      loginForm.querySelector('#login-pass').value = '';
      setTimeout(() => loginError.classList.remove('show'), 3500);
    }
  });

  /* Logout */
  navUser?.addEventListener('click', () => {
    localStorage.removeItem('lugos_session');
    navUser.classList.remove('visible');
    if (navLogin) navLogin.style.display = '';
    showToast('Vous êtes déconnecté(e).');
  });

  function openLogin()  { overlay?.classList.add('open'); document.body.style.overflow = 'hidden'; }
  function closeLogin() { overlay?.classList.remove('open'); document.body.style.overflow = ''; }
  function setLoggedIn(sess) {
    if (navLogin) navLogin.style.display = 'none';
    if (navUser) { navUser.classList.add('visible'); }
    if (navUserName) navUserName.textContent = sess.name;
  }

  /* Toast notification */
  function showToast(msg) {
    const t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    document.body.appendChild(t);
    requestAnimationFrame(() => t.classList.add('show'));
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 400); }, 3000);
  }

  /* Toast styles (injected) */
  const toastCSS = `
    .toast {
      position:fixed; bottom:2rem; right:2rem; z-index:9999;
      background:var(--vert-foret); color:#fff;
      padding:.9rem 1.5rem; border-radius:99px;
      font-size:.88rem; font-weight:600;
      box-shadow:0 8px 30px rgba(0,0,0,.2);
      transform:translateY(20px); opacity:0;
      transition:all .35s cubic-bezier(.34,1.56,.64,1);
    }
    .toast.show { transform:none; opacity:1; }
  `;
  const style = document.createElement('style');
  style.textContent = toastCSS;
  document.head.appendChild(style);

});
