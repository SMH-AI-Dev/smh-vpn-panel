/* DOM and formatting helpers. */
import { t } from "./i18n.js";

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else if (key.startsWith("on") && typeof value === "function")
      node.addEventListener(key.slice(2), value);
    else if (key === "dataset") Object.assign(node.dataset, value);
    else node.setAttribute(key, value);
  }
  appendChildren(node, children);
  return node;
}

function appendChildren(node, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function fmtBytes(value) {
  let n = Number(value) || 0;
  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${n >= 100 || i === 0 ? Math.round(n) : n.toFixed(1)} ${units[i]}`;
}

export function fmtDate(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString("en-GB", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtJalali(iso) {
  if (!iso) return "";
  try {
    return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
      dateStyle: "medium",
    }).format(new Date(iso));
  } catch (err) {
    return "";
  }
}

export function fmtDuration(seconds) {
  let s = Math.max(0, Number(seconds) || 0);
  const days = Math.floor(s / 86400);
  s -= days * 86400;
  const hours = Math.floor(s / 3600);
  s -= hours * 3600;
  const minutes = Math.floor(s / 60);
  return `${days}d ${hours}h ${minutes}m`;
}

export function spinner() {
  return el("div", { class: "empty" }, el("span", { class: "spin" }), " ", t("loading"));
}

let toastHost = null;
export function toast(message, type = "info", duration = 3400) {
  if (!toastHost) {
    toastHost = el("div", { class: "toasts" });
    document.body.append(toastHost);
  }
  const node = el("div", { class: `toast ${type}` }, message);
  toastHost.append(node);
  setTimeout(() => node.remove(), duration);
}

export function openModal({ title, body, footer, wide = false }) {
  const overlay = el("div", { class: "overlay" });
  const modal = el("div", { class: `modal${wide ? " wide" : ""}` });
  const close = () => overlay.remove();
  const head = el(
    "div",
    { class: "modal-head" },
    el("div", {}, title),
    el("button", { class: "x-btn", onclick: close, type: "button" }, "×")
  );
  const bodyEl = el("div", { class: "modal-body" });
  appendChildren(bodyEl, [body]);
  modal.append(head, bodyEl);
  if (footer) {
    const footEl = el("div", { class: "modal-foot" });
    appendChildren(footEl, [footer]);
    modal.append(footEl);
  }
  overlay.append(modal);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) close();
  });
  document.body.append(overlay);
  return { close, overlay, modal, body: bodyEl };
}

export function confirmDialog(message) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      modal.close();
      resolve(value);
    };
    const modal = openModal({
      title: t("confirm_delete_title"),
      body: el("p", {}, message),
      footer: [
        el(
          "button",
          { class: "btn danger", type: "button", onclick: () => finish(true) },
          t("yes_delete")
        ),
        el(
          "button",
          { class: "btn ghost", type: "button", onclick: () => finish(false) },
          t("cancel")
        ),
      ],
    });
    modal.overlay.addEventListener("click", (event) => {
      if (event.target === modal.overlay) finish(false);
    });
  });
}

export async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch (err) {
    const area = document.createElement("textarea");
    area.value = text;
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.append(area);
    area.select();
    try {
      document.execCommand("copy");
    } catch (err2) {
      /* ignore */
    }
    area.remove();
  }
  toast(t("copied"), "success", 1500);
}

export function badge(text, kind = "b-mut") {
  return el("span", { class: `badge ${kind}` }, text);
}

export function progressEl(used, quota) {
  const wrap = el("div", { class: "progress", title: "" });
  const fill = el("div", { class: "fill" });
  let percent = 0;
  if (quota && quota > 0) {
    percent = Math.min(100, Math.round((used / (quota * 1024 ** 3)) * 100));
  } else {
    percent = 0;
  }
  fill.style.width = `${quota && quota > 0 ? Math.max(2, percent) : 100}%`;
  if (!quota || quota <= 0) fill.classList.add("ok");
  else if (percent >= 90) fill.classList.add("err");
  else if (percent >= 70) fill.classList.add("warn");
  wrap.append(fill);
  return wrap;
}

export function serviceBadge(state) {
  const map = {
    active: ["b-ok", t("active")],
    inactive: ["b-err", t("inactive")],
    disabled: ["b-mut", t("disabled")],
    unknown: ["b-warn", t("unknown")],
  };
  const [kind, label] = map[state] || ["b-mut", state];
  return badge(label, kind);
}

export function clientStatusBadge(client) {
  if (client.enabled) return badge(t("active"), "b-ok");
  const reasons = {
    quota: t("reason_quota_text"),
    expiry: t("reason_expiry_text"),
    manual: t("reason_manual_text"),
  };
  return badge(reasons[client.disabled_reason] || t("inactive"), "b-err");
}
