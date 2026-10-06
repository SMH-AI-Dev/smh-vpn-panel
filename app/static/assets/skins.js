/* SMH Panel — "UI environments" (skins) system.
 *
 * Sources (extracted from the sample panel projects the user provided):
 *  - HyprPanel themes collection -> 45 environments (see ./skins-hypr.js)
 *  - PasarGuard dashboard theme system: the base/accent palette formulas and
 *    the vega/nova/maia/lyra style presets are ported from
 *    panel-main/dashboard/src/constants/color-themes.ts
 *  - SMH Panel defaults.
 */
import { HYPR_SKINS } from "./skins-hypr.js";

/* ------------------------------- helpers ------------------------------- */
export function hexToRgb(hex) {
  let h = String(hex || "").trim().replace(/^#/, "");
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  if (!/^[0-9a-fA-F]{6}$/.test(h)) h = "4c8dff";
  return {
    r: parseInt(h.slice(0, 2), 16),
    g: parseInt(h.slice(2, 4), 16),
    b: parseInt(h.slice(4, 6), 16),
  };
}

function toHex(rgb) {
  const f = (n) => Math.min(255, Math.max(0, Math.round(n))).toString(16).padStart(2, "0");
  return `#${f(rgb.r)}${f(rgb.g)}${f(rgb.b)}`;
}

export function mixColors(a, b, w) {
  const A = hexToRgb(a);
  const B = hexToRgb(b);
  return toHex({
    r: A.r + (B.r - A.r) * w,
    g: A.g + (B.g - A.g) * w,
    b: A.b + (B.b - A.b) * w,
  });
}

export function rgbaColor(hex, alpha) {
  const c = hexToRgb(hex);
  return `rgba(${c.r}, ${c.g}, ${c.b}, ${alpha})`;
}

function luminance(hex) {
  const c = hexToRgb(hex);
  return (0.299 * c.r + 0.587 * c.g + 0.114 * c.b) / 255;
}

/* --------------------------- default skins ----------------------------- */
const DEFAULT_SKINS = [
  {
    id: "default-dark",
    name: "کلاسیک تیره",
    source: "SMH Panel",
    variant: "base",
    pal: {
      bg: "#0e1116", panel: "#161b23", panel2: "#1b2230", border: "#242c39",
      text: "#e8ecf3", muted: "#8e9bb0", accent: "#4c8dff", accent2: "#2f6fe4",
      ok: "#3ecf8e", warn: "#f5a623", err: "#ff6b6b",
    },
  },
  {
    id: "default-light",
    name: "کلاسیک روشن",
    source: "SMH Panel",
    variant: "base",
    pal: {
      bg: "#f3f5f9", panel: "#ffffff", panel2: "#f6f8fc", border: "#dbe1ea",
      text: "#17202e", muted: "#5b687f", accent: "#2f6fe4", accent2: "#2456b8",
      ok: "#1d9e66", warn: "#b87700", err: "#d64545",
    },
  },
];

/* ------------------- PasarGuard system (ported) ------------------------ */
function hslToHex(h, s, l) {
  s /= 100;
  l /= 100;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  const to = (x) => Math.round(255 * x).toString(16).padStart(2, "0");
  return `#${to(f(0))}${to(f(8))}${to(f(4))}`;
}

const PG_SURFACES = {
  Neutral: { h: 240, ls: 5, ds: 2 },
  Zinc: { h: 240, ls: 6, ds: 3 },
  Slate: { h: 215, ls: 14, ds: 8 },
  Stone: { h: 30, ls: 6, ds: 4 },
  Gray: { h: 0, ls: 4, ds: 2 },
  Mauve: { h: 280, ls: 8, ds: 5 },
  Olive: { h: 85, ls: 8, ds: 5 },
  Mist: { h: 200, ls: 10, ds: 6 },
};

const PG_ACCENTS = {
  red: [0, 72, 51], rose: [347, 77, 50], pink: [322, 79, 52], orange: [21, 90, 48],
  amber: [38, 92, 50], yellow: [48, 96, 53], green: [142, 71, 45], teal: [173, 80, 40],
  cyan: [189, 94, 48], blue: [217, 91, 60], indigo: [234, 89, 64], violet: [263, 70, 50],
};

function pgSkin(baseKey, accentKey, mode) {
  const b = PG_SURFACES[baseKey];
  const [ah, as, al] = PG_ACCENTS[accentKey];
  const accent = hslToHex(ah, as, al);
  if (mode === "light") {
    return {
      bg: hslToHex(b.h, b.ls, 96),
      panel: hslToHex(b.h, b.ls, 98),
      panel2: hslToHex(b.h, b.ls, 90),
      border: hslToHex(b.h, b.ls, 80),
      text: hslToHex(b.h, Math.min(b.ls + 2, 10), 10),
      muted: hslToHex(b.h, b.ls, 40),
      accent,
      accent2: mixColors(accent, "#000000", 0.25),
      ok: hslToHex(142, 71, 40),
      warn: hslToHex(38, 92, 45),
      err: hslToHex(0, 72, 51),
    };
  }
  return {
    bg: hslToHex(b.h, b.ds, 11),
    panel: hslToHex(b.h, b.ds, 12.5),
    panel2: hslToHex(b.h, b.ds + 2, 16),
    border: hslToHex(b.h, b.ds, 18),
    text: hslToHex(b.h, b.ds, 98),
    muted: hslToHex(b.h, b.ds, 64),
    accent,
    accent2: mixColors(accent, "#ffffff", 0.2),
    ok: hslToHex(142, 71, 45),
    warn: hslToHex(38, 92, 50),
    err: hslToHex(0, 72, 51),
  };
}

const PG_COMBOS = [
  ["pg-slate-blue-dark", "Slate · Blue", "Slate", "blue", "dark"],
  ["pg-slate-cyan-dark", "Slate · Cyan", "Slate", "cyan", "dark"],
  ["pg-zinc-violet-dark", "Zinc · Violet", "Zinc", "violet", "dark"],
  ["pg-neutral-indigo-dark", "Neutral · Indigo", "Neutral", "indigo", "dark"],
  ["pg-mauve-rose-dark", "Mauve · Rose", "Mauve", "rose", "dark"],
  ["pg-olive-green-dark", "Olive · Green", "Olive", "green", "dark"],
  ["pg-mist-teal-dark", "Mist · Teal", "Mist", "teal", "dark"],
  ["pg-stone-amber-dark", "Stone · Amber", "Stone", "amber", "dark"],
  ["pg-gray-red-dark", "Gray · Red", "Gray", "red", "dark"],
  ["pg-slate-blue-light", "Slate · Blue", "Slate", "blue", "light"],
  ["pg-zinc-green-light", "Zinc · Green", "Zinc", "green", "light"],
  ["pg-mist-cyan-light", "Mist · Cyan", "Mist", "cyan", "light"],
  ["pg-stone-amber-light", "Stone · Amber", "Stone", "amber", "light"],
  ["pg-mauve-violet-light", "Mauve · Violet", "Mauve", "violet", "light"],
  ["pg-neutral-teal-light", "Neutral · Teal", "Neutral", "teal", "light"],
  ["pg-olive-green-light", "Olive · Green", "Olive", "green", "light"],
];

const PG_SKINS = PG_COMBOS.map(([id, label, baseKey, accentKey, mode]) => ({
  id,
  name: `${label} (${mode === "light" ? "روشن" : "تیره"})`,
  source: "PasarGuard",
  variant: mode,
  pal: pgSkin(baseKey, accentKey, mode),
}));

/* ------------------------------ layouts -------------------------------- */
/* Ported from PasarGuard themeStylePresets (vega/nova/maia/lyra). */
export const LAYOUTS = [
  { id: "vega", name: "وگا — راحت", src: "PasarGuard", density: "comfortable", surface: "subtle", radius: "14px" },
  { id: "nova", name: "نوا — فشرده", src: "PasarGuard", density: "compact", surface: "flat", radius: "8px" },
  { id: "maia", name: "مایا — جادار", src: "PasarGuard", density: "spacious", surface: "elevated", radius: "18px" },
  { id: "lyra", name: "لیرا — صاف", src: "PasarGuard", density: "compact", surface: "flat", radius: "2px" },
];

/* ----------------------------- apply/save ------------------------------ */
export const ALL_SKINS = [...DEFAULT_SKINS, ...PG_SKINS, ...HYPR_SKINS];

export function applySkin(skin) {
  const p = skin.pal;
  const root = document.documentElement;
  const dark = luminance(p.bg) < 0.5;
  const set = (k, v) => root.style.setProperty(k, v);

  set("--bg", p.bg);
  set("--bg-soft", p.bgSoft || mixColors(p.bg, p.panel, 0.55));
  set("--panel", p.panel);
  set("--panel-2", p.panel2 || mixColors(p.panel, p.bg, 0.35));
  set("--border", p.border);
  set("--text", p.text);
  set("--muted", p.muted);
  set("--accent", p.accent);
  set("--accent-2", p.accent2 || mixColors(p.accent, p.text, 0.25));
  set("--accent-soft", rgbaColor(p.accent, dark ? 0.16 : 0.12));
  set("--ok", p.ok || "#3ecf8e");
  set("--warn", p.warn || "#f5a623");
  set("--err", p.err || "#ff6b6b");
  set("--shadow", dark ? "0 10px 28px rgba(0,0,0,.42)" : "0 10px 26px rgba(25,34,52,.12)");
  set(
    "--hero-grad",
    `linear-gradient(135deg, ${rgbaColor(p.accent, dark ? 0.2 : 0.14)}, ${rgbaColor(
      p.accent2 || p.accent,
      dark ? 0.14 : 0.09
    )}), ${p.panel}`
  );
  root.dataset.mode = dark ? "dark" : "light";
  root.dataset.skin = skin.id;
}

export function applyLayout(id) {
  const layout = LAYOUTS.find((item) => item.id === id) || LAYOUTS[0];
  const root = document.documentElement;
  root.dataset.density = layout.density;
  root.dataset.surface = layout.surface;
  root.style.setProperty("--radius", layout.radius);
  const small = Math.max(2, parseInt(layout.radius, 10) - 4);
  root.style.setProperty("--radius-sm", `${small}px`);
}

export function applySaved() {
  const skinId = localStorage.getItem("smh_skin") || "default-dark";
  const skin = ALL_SKINS.find((item) => item.id === skinId) || ALL_SKINS[0];
  applySkin(skin);
  applyLayout(localStorage.getItem("smh_layout") || "vega");
  try {
    localStorage.removeItem("smh_theme"); // old color-only themes removed
  } catch (err) {
    /* ignore */
  }
}
