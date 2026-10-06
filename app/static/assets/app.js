/* App shell: router, sidebar, session bootstrap. */
import { t, setLang } from "./i18n.js";
import { api } from "./api.js";
import { el } from "./ui.js";
import { state } from "./state.js";
import * as pages from "./pages.js";

const ICONS = {
  dashboard:
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="5" rx="2"/><rect x="13" y="10" width="8" height="11" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/></svg>',
  inbounds:
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h13M4 7l3-3M4 7l3 3"/><path d="M20 17H7m13 0l-3-3m3 3l-3 3"/></svg>',
  clients:
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="8" r="3.5"/><path d="M5 20c1.2-3.4 3.9-5 7-5s5.8 1.6 7 5"/></svg>',
  settings:
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 15.5A3.5 3.5 0 1 0 12 8.5a3.5 3.5 0 0 0 0 7z"/><path d="M19 12a7 7 0 0 0-.14-1.4l2.1-1.63-2-3.46-2.48 1a7 7 0 0 0-2.42-1.4L13.7 2.5h-3.4l-.36 2.6a7 7 0 0 0-2.42 1.4l-2.48-.99-2 3.46 2.1 1.63A7 7 0 0 0 5 12c0 .48.05.94.14 1.4l-2.1 1.63 2 3.46 2.48-1a7 7 0 0 0 2.42 1.4l.36 2.61h3.4l.36-2.6a7 7 0 0 0 2.42-1.4l2.48.99 2-3.46-2.1-1.63c.09-.46.14-.92.14-1.4z"/></svg>',
  logs:
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 4h14v16H5z"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>',
  help:
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.2A2.5 2.5 0 1 1 12 12v1.4"/><circle cx="12" cy="17" r=".6" fill="currentColor"/></svg>',
  about:
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 3l2.6 5.3 5.9.9-4.2 4.1 1 5.8L12 16.4 6.7 19l1-5.8L3.5 9.2l5.9-.9z"/></svg>',
};

const NAV = [
  ["dashboard", "nav_dashboard"],
  ["inbounds", "nav_inbounds"],
  ["clients", "nav_clients"],
  ["settings", "nav_settings"],
  ["logs", "nav_logs"],
  ["help", "nav_help"],
  ["about", "nav_about"],
];

function parseRoute() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [page, arg] = raw.split("/");
  return { page: page || "dashboard", arg: arg || null };
}

function applyChrome() {
  const theme = localStorage.getItem("smh_theme") || "dark";
  document.documentElement.dataset.theme = theme;
  setLang(localStorage.getItem("smh_lang") || "fa");
}

function renderShell(root) {
  const route = parseRoute();
  const activePage = route.page;

  const nav = el("nav", { class: "nav" });
  for (const [key, labelKey] of NAV) {
    const item = el(
      "a",
      {
        class: `nav-item${activePage === key ? " active" : ""}`,
        href: `#/${key}`,
        html: `<span class="ico">${ICONS[key]}</span><span>${t(labelKey)}</span>`,
      }
    );
    nav.append(item);
  }

  const sidebar = el(
    "aside",
    { class: "sidebar" },
    el(
      "div",
      { class: "brand" },
      el("div", { class: "logo" }, "S"),
      el(
        "div",
        {},
        el("div", { class: "name" }, t("app_title")),
        el("div", { class: "ver" }, state.me ? `v${state.me.version} · ${state.me.username}` : "")
      )
    ),
    nav,
    el(
      "div",
      { class: "sidebar-footer" },
      el(
        "button",
        {
          class: "btn sm ghost",
          type: "button",
          onclick: () => pages.openThemePicker(),
        },
        "🎨 " + t("theme")
      ),
      el(
        "button",
        {
          class: "btn sm ghost",
          type: "button",
          onclick: () => {
            const next = localStorage.getItem("smh_lang") === "en" ? "fa" : "en";
            localStorage.setItem("smh_lang", next);
            boot();
          },
        },
        t("lang_switch")
      ),
      el(
        "button",
        {
          class: "btn sm danger",
          type: "button",
          onclick: async () => {
            await api.logout();
            location.hash = "#/login";
          },
        },
        t("logout")
      )
    )
  );

  const titleKey = (NAV.find(([key]) => key === activePage) || NAV[0])[1];
  const topbar = el(
    "div",
    { class: "topbar" },
    el("div", { class: "topbar-title" }, t(titleKey))
  );

  const content = el("div", { class: "content", id: "content" });
  const main = el("div", { class: "main" }, topbar, content);
  root.append(el("div", { class: "app" }, sidebar, main));
  return content;
}

async function renderPage(content, route) {
  if (route.page === "inbounds" && route.arg) {
    await pages.inboundDetail(content, route.arg);
    return;
  }
  const handler = pages[route.page] || pages.dashboard;
  await handler(content);
}

export async function boot() {
  applyChrome();
  const root = document.getElementById("app");
  root.innerHTML = "";
  const route = parseRoute();

  if (route.page === "login") {
    document.body.classList.add("login-body");
    pages.login(root);
    return;
  }
  document.body.classList.remove("login-body");

  try {
    state.me = await api.get("/api/auth/me");
  } catch (err) {
    if (err.status === 401) {
      location.hash = "#/login";
      return;
    }
    throw err;
  }

  const content = renderShell(root);
  try {
    await renderPage(content, route);
  } catch (err) {
    content.append(
      el("div", { class: "card" }, el("div", { class: "error-text" }, `${t("error")}: ${err.message}`))
    );
  }
}

if (typeof document !== "undefined") {
  boot();
  window.addEventListener("hashchange", boot);
}
