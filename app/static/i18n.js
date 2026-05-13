const TRANSLATIONS = {
  en: {
    "nav.name": "Name",
    "nav.play": "Play",
    "nav.leaderboard": "Leaderboard",
    "name.title": "Enter your name",
    "name.placeholder": "Your name",
    "name.start": "Play",
    "name.error_empty": "Please enter a name.",
    "name.error_too_long": "Name must be 20 characters or fewer.",
    "name.error_invalid_chars": "Name contains invalid characters.",
    "play.score": "Apples: {score}",
    "play.paused": "Paused",
    "play.resume_hint": "Press Space to pause/resume",
    "over.title": "Game Over",
    "over.score": "You ate {score} apples",
    "over.reason_wall": "You hit a wall.",
    "over.reason_self": "You ran into yourself.",
    "over.reason_bad_apple": "You ate a bad apple.",
    "over.rank": "Rank: #{rank}",
    "over.no_rank": "Not in top 10.",
    "over.play_again": "Play again",
    "lb.title": "Leaderboard",
    "lb.col_rank": "#",
    "lb.col_name": "Name",
    "lb.col_score": "Apples",
    "lb.empty": "No scores yet.",
  },
  de: {
    "nav.name": "Name",
    "nav.play": "Spielen",
    "nav.leaderboard": "Bestenliste",
    "name.title": "Gib deinen Namen ein",
    "name.placeholder": "Dein Name",
    "name.start": "Spielen",
    "name.error_empty": "Bitte gib einen Namen ein.",
    "name.error_too_long": "Name darf höchstens 20 Zeichen lang sein.",
    "name.error_invalid_chars": "Name enthält ungültige Zeichen.",
    "play.score": "Äpfel: {score}",
    "play.paused": "Pausiert",
    "play.resume_hint": "Leertaste zum Pausieren/Fortsetzen",
    "over.title": "Spiel vorbei",
    "over.score": "Du hast {score} Äpfel gegessen",
    "over.reason_wall": "Du bist gegen eine Wand gestoßen.",
    "over.reason_self": "Du bist in dich selbst gelaufen.",
    "over.reason_bad_apple": "Du hast einen schlechten Apfel gegessen.",
    "over.rank": "Platz: #{rank}",
    "over.no_rank": "Nicht in den Top 10.",
    "over.play_again": "Nochmal spielen",
    "lb.title": "Bestenliste",
    "lb.col_rank": "#",
    "lb.col_name": "Name",
    "lb.col_score": "Äpfel",
    "lb.empty": "Noch keine Ergebnisse.",
  },
  es: {
    "nav.name": "Nombre",
    "nav.play": "Jugar",
    "nav.leaderboard": "Clasificación",
    "name.title": "Introduce tu nombre",
    "name.placeholder": "Tu nombre",
    "name.start": "Jugar",
    "name.error_empty": "Introduce un nombre.",
    "name.error_too_long": "El nombre debe tener 20 caracteres o menos.",
    "name.error_invalid_chars": "El nombre contiene caracteres no válidos.",
    "play.score": "Manzanas: {score}",
    "play.paused": "Pausado",
    "play.resume_hint": "Pulsa Espacio para pausar/reanudar",
    "over.title": "Fin del juego",
    "over.score": "Comiste {score} manzanas",
    "over.reason_wall": "Chocaste con una pared.",
    "over.reason_self": "Chocaste contigo mismo.",
    "over.reason_bad_apple": "Comiste una manzana mala.",
    "over.rank": "Puesto: #{rank}",
    "over.no_rank": "No estás en el top 10.",
    "over.play_again": "Jugar otra vez",
    "lb.title": "Clasificación",
    "lb.col_rank": "#",
    "lb.col_name": "Nombre",
    "lb.col_score": "Manzanas",
    "lb.empty": "Aún no hay puntuaciones.",
  },
};

const SUPPORTED = ["en", "de", "es"];
let currentLang = "en";

function detectLang() {
  const stored = localStorage.getItem("lang");
  if (stored && SUPPORTED.indexOf(stored) >= 0) return stored;
  const candidates = navigator.languages || [navigator.language || "en"];
  for (const candidate of candidates) {
    const short = candidate.slice(0, 2).toLowerCase();
    if (SUPPORTED.indexOf(short) >= 0) return short;
  }
  return "en";
}

function t(key, vars) {
  vars = vars || {};
  const dict = TRANSLATIONS[currentLang] || TRANSLATIONS.en;
  let str = dict[key] || TRANSLATIONS.en[key] || key;
  for (const k of Object.keys(vars)) {
    str = str.split("{" + k + "}").join(String(vars[k]));
  }
  return str;
}

function applyTranslations(root) {
  root = root || document;
  for (const el of root.querySelectorAll("[data-i18n]")) {
    el.textContent = t(el.dataset.i18n);
  }
  for (const el of root.querySelectorAll("[data-i18n-placeholder]")) {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  }
}

function setLang(lang) {
  if (SUPPORTED.indexOf(lang) < 0) return;
  currentLang = lang;
  localStorage.setItem("lang", lang);
  document.documentElement.lang = lang;
  applyTranslations();
  document.dispatchEvent(new CustomEvent("langchange", { detail: { lang: lang } }));
}

window.i18n = {
  t: t,
  setLang: setLang,
  applyTranslations: applyTranslations,
  detectLang: detectLang,
  getLang: function () { return currentLang; },
};
