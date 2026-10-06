/* Page renderers. */
import { t, getLang } from "./i18n.js";
import { api } from "./api.js";
import {
  el,
  toast,
  confirmDialog,
  copyText,
  openModal,
  badge,
  progressEl,
  fmtBytes,
  fmtDate,
  fmtJalali,
  fmtDuration,
  spinner,
  serviceBadge,
  clientStatusBadge,
} from "./ui.js";
import { state } from "./state.js";

const PROTOCOLS = ["vless", "vmess", "trojan", "shadowsocks", "wireguard"];
const SS_METHODS = [
  "2022-blake3-aes-256-gcm",
  "2022-blake3-aes-128-gcm",
  "2022-blake3-chacha20-poly1305",
  "aes-256-gcm",
  "chacha20-ietf-poly1305",
];

const num = (value) => Number(value) || 0;

function reroute() {
  window.dispatchEvent(new HashChangeEvent("hashchange"));
}

function rerender(root, fn, ...args) {
  root.innerHTML = "";
  fn(root, ...args);
}

function pageHeader(title, actions = []) {
  return el(
    "div",
    { class: "row between mb" },
    el("h3", {}, title),
    el("div", { class: "row" }, ...actions)
  );
}

function card(title, ...children) {
  return el(
    "div",
    { class: "card" },
    title ? el("div", { class: "card-title" }, title) : null,
    ...children
  );
}

function field(label, input, hint) {
  return el(
    "div",
    { class: "field" },
    el("label", { class: "label" }, label),
    input,
    hint ? el("div", { class: "hint" }, hint) : null
  );
}

function grid(...children) {
  return el("div", { class: "form-grid" }, ...children);
}

function toggle(node, visible) {
  node.style.display = visible ? "" : "none";
}

function emptyCard() {
  return el("div", { class: "card empty" }, t("empty_data"));
}

function copyBtn(text) {
  return el(
    "button",
    { class: "btn sm", type: "button", onclick: () => copyText(text) },
    t("btn_copy")
  );
}

function switchEl(checked, onchange) {
  const input = el("input", { type: "checkbox" });
  input.checked = Boolean(checked);
  input.addEventListener("change", () => onchange(input.checked));
  return el("label", { class: "switch" }, input, el("span", { class: "track" }));
}

function percentBar(percent) {
  const wrap = el("div", { class: "progress" });
  const fill = el("div", {
    class: "fill",
    style: `width:${Math.min(100, Math.max(3, Math.round(percent)))}%`,
  });
  if (percent >= 90) fill.classList.add("err");
  else if (percent >= 70) fill.classList.add("warn");
  else fill.classList.add("ok");
  wrap.append(fill);
  return wrap;
}

function reportApply(result) {
  if (result && result.apply_error) {
    toast(t("apply_error") + result.apply_error, "warn", 7000);
  }
}

/* ------------------------------- login -------------------------------- */
export function login(root) {
  const username = el("input", { class: "input", autocomplete: "username" });
  const password = el("input", {
    class: "input",
    type: "password",
    autocomplete: "current-password",
  });
  const errorBox = el("div", { class: "error-text" });

  const submit = async (event) => {
    if (event) event.preventDefault();
    errorBox.textContent = "";
    try {
      await api.login(username.value.trim(), password.value);
      location.hash = "#/dashboard";
      if (location.hash === "#/dashboard") reroute();
    } catch (err) {
      errorBox.textContent =
        err.status === 429
          ? "تعداد تلاش‌ها بیش از حد مجاز است — کمی بعد دوباره امتحان کن"
          : t("login_failed");
    }
  };

  root.append(
    el(
      "form",
      { onsubmit: submit },
      el(
        "div",
        { class: "card login-card" },
        el(
          "div",
          { class: "brand" },
          el("div", { class: "logo" }, "S"),
          el("div", { class: "name" }, t("app_title"))
        ),
        el("h3", { class: "center" }, t("login_welcome")),
        field(t("login_user"), username),
        field(t("login_pass"), password),
        errorBox,
        el(
          "button",
          { class: "btn primary", type: "submit", style: "width:100%" },
          t("login_btn")
        )
      )
    )
  );
}

/* ----------------------------- dashboard ------------------------------ */
export async function dashboard(root) {
  root.append(
    pageHeader(t("nav_dashboard"), [
      el(
        "button",
        {
          class: "btn",
          type: "button",
          onclick: () => rerender(root, dashboard),
        },
        t("btn_refresh")
      ),
    ])
  );

  const grid = el("div", { class: "grid cards-3" });
  const specsCard = card(t("specs_title"));
  const chartCard = card(t("dash_traffic_24h"));
  root.append(
    grid,
    el("div", { class: "grid" }, specsCard),
    el("div", { class: "grid" }, chartCard)
  );
  grid.append(card(null, spinner()), card(null, spinner()), card(null, spinner()));

  let status;
  let samples = [];
  [status, samples] = await Promise.all([
    api.get("/api/system/status"),
    api.get("/api/system/traffic?hours=24").catch(() => []),
  ]);

  grid.innerHTML = "";

  const services = card(t("dash_services"));
  for (const [key, label] of [
    ["xray", t("svc_xray")],
    ["wg", t("svc_wg")],
    ["panel", t("svc_panel")],
  ]) {
    const serviceState = (status.services || {})[key] || "unknown";
    services.append(
      el(
        "div",
        { class: "row between", style: "padding:5px 0" },
        el("div", {}, label),
        el(
          "div",
          { class: "row" },
          serviceBadge(serviceState),
          key !== "panel"
            ? el(
                "button",
                {
                  class: "btn sm",
                  type: "button",
                  onclick: () => restartService(key, root),
                },
                t("restart")
              )
            : null
        )
      )
    );
  }
  services.append(
    el("div", { class: "divider" }),
    el(
      "div",
      { class: "kv" },
      el("div", { class: "k" }, t("version")),
      el("div", { class: "mono small" }, status.xray_version || "—"),
      el("div", { class: "k" }, t("uptime")),
      el("div", { class: "small" }, fmtDuration(status.uptime_sec)),
      el("div", { class: "k" }, "Mode"),
      el("div", { class: "small" }, status.dev_mode ? "DEV" : "Production")
    )
  );

  const resources = card(t("dash_resources"));
  const resRow = (label, percent, detail) =>
    el(
      "div",
      { style: "margin-bottom:10px" },
      el(
        "div",
        { class: "row between" },
        el("span", {}, label),
        el("span", { class: "muted small" }, detail)
      ),
      percentBar(percent)
    );
  const memFree = status.mem.available != null ? status.mem.available : status.mem.free;
  resources.append(
    resRow(t("cpu"), status.cpu_percent, `${Math.round(status.cpu_percent)}%`),
    resRow(
      t("ram"),
      status.mem.percent,
      `${t("spec_used")} ${fmtBytes(status.mem.used)} / ${t("spec_total")} ${fmtBytes(status.mem.total)} · ${t("spec_free")} ${fmtBytes(memFree)}`
    ),
    resRow(
      t("disk"),
      status.disk.percent,
      `${t("spec_used")} ${fmtBytes(status.disk.used)} / ${t("spec_total")} ${fmtBytes(status.disk.total)} · ${t("spec_free")} ${fmtBytes(status.disk.free)}`
    )
  );

  const totals = card(t("dash_counts"));
  const countRow = (label, value) =>
    el("div", { class: "row between" }, el("span", {}, label), el("b", {}, String(value)));
  totals.append(
    countRow(t("count_inbounds"), status.counts.inbounds),
    countRow(t("count_clients"), status.counts.clients),
    countRow(t("count_active"), status.counts.active_clients),
    el("div", { class: "divider" }),
    countRow(t("total_up"), fmtBytes(status.totals.up)),
    countRow(t("total_down"), fmtBytes(status.totals.down))
  );

  grid.append(services, resources, totals);

  const specs = status.specs || {};
  const specRow = (label, value) =>
    el(
      "div",
      { class: "row between", style: "padding:3px 0; gap:12px" },
      el("span", { class: "muted small" }, label),
      el("span", { class: "small", style: "text-align:left; word-break:break-word" }, value)
    );
  specsCard.append(
    specRow(t("spec_hostname"), specs.hostname || "—"),
    specRow(t("spec_os"), specs.os || "—"),
    specRow(t("spec_kernel"), `${specs.kernel || "—"} · ${specs.arch || "—"}`),
    specRow(t("spec_cpu"), specs.cpu_model || "—"),
    specRow(
      t("spec_cores"),
      t("spec_cores_fmt", specs.cores_physical ?? "—", specs.cores_logical ?? "—") +
        (specs.cpu_freq_mhz ? ` · ${specs.cpu_freq_mhz} MHz` : "")
    ),
    specs.load_avg ? specRow(t("spec_load"), specs.load_avg.join(" · ")) : null,
    el("div", { class: "label", style: "margin-top:8px" }, t("spec_mem")),
    specRow(t("spec_total"), fmtBytes(status.mem.total)),
    specRow(t("spec_used"), `${fmtBytes(status.mem.used)} (${status.mem.percent}%)`),
    specRow(t("spec_free"), fmtBytes(memFree)),
    specRow(
      t("spec_swap"),
      status.swap && status.swap.total > 0
        ? `${fmtBytes(status.swap.used)} / ${fmtBytes(status.swap.total)} (${status.swap.percent}%)`
        : t("spec_disabled")
    ),
    specRow(
      t("spec_disk_root"),
      `${fmtBytes(status.disk.used)} / ${fmtBytes(status.disk.total)} · ${t("spec_free")}: ${fmtBytes(status.disk.free)} (${status.disk.percent}%)`
    ),
    specRow(t("uptime"), fmtDuration(status.uptime_sec))
  );

  chartCard.append(renderChart(samples));
}

async function restartService(name, root) {
  try {
    await api.post(`/api/system/service/${name}/restart`);
    toast(`${name}: ${t("restart")} ✓`, "success");
  } catch (err) {
    toast(err.message, "error", 6000);
  }
  rerender(root, dashboard);
}

function renderChart(samples) {
  const box = el("div", { class: "chart-box" });
  const canvas = el("canvas");
  box.append(canvas);
  requestAnimationFrame(() => drawChart(canvas, samples));
  return box;
}

function drawChart(canvas, samples) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(320, rect.width);
  const height = Math.max(110, rect.height);
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  const accent = getComputedStyle(document.documentElement)
    .getPropertyValue("--accent")
    .trim() || "#4c8dff";

  const nowHour = Math.floor(Date.now() / 3600000);
  const buckets = new Array(24).fill(0);
  for (const sample of samples || []) {
    const hour = Math.floor((sample.ts * 1000) / 3600000);
    const index = 23 - (nowHour - hour);
    if (index >= 0 && index < 24) buckets[index] += (sample.up || 0) + (sample.down || 0);
  }
  const max = Math.max(1, ...buckets);
  const barWidth = width / 24;

  ctx.clearRect(0, 0, width, height);
  buckets.forEach((value, index) => {
    const barHeight = Math.max(3, (value / max) * (height - 26));
    const x = index * barWidth + 2;
    const y = height - 20 - barHeight;
    ctx.fillStyle = value === 0 ? "rgba(128,128,128,.16)" : accent;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, Math.max(3, barWidth - 5), barHeight, 3);
    else ctx.rect(x, y, Math.max(3, barWidth - 5), barHeight);
    ctx.fill();
    if (index % 6 === 0) {
      ctx.fillStyle = "rgba(128,128,128,.75)";
      ctx.font = "10px sans-serif";
      const hour = new Date((nowHour - (23 - index)) * 3600000).getHours();
      ctx.fillText(`${String(hour).padStart(2, "0")}:00`, x - 4, height - 6);
    }
  });
}

/* ------------------------------ inbounds ------------------------------ */
export async function inbounds(root) {
  root.append(
    pageHeader(t("nav_inbounds"), [
      el(
        "button",
        { class: "btn", type: "button", onclick: () => rerender(root, inbounds) },
        t("btn_refresh")
      ),
      el(
        "button",
        { class: "btn primary", type: "button", onclick: () => inboundModal(root) },
        t("btn_new_inbound")
      ),
    ])
  );

  const holder = el("div");
  root.append(holder);
  holder.append(spinner());

  const rows = await api.get("/api/inbounds");
  holder.innerHTML = "";
  if (!rows.length) {
    holder.append(emptyCard());
    return;
  }

  const table = el("table", { class: "table" });
  table.append(
    el(
      "thead",
      {},
      el(
        "tr",
        {},
        el("th", {}, t("th_tag")),
        el("th", {}, t("th_protocol")),
        el("th", {}, t("th_port")),
        el("th", {}, t("th_status")),
        el("th", {}, t("th_clients")),
        el("th", {}, t("th_traffic")),
        el("th", {}, t("th_actions"))
      )
    )
  );
  const tbody = el("tbody", {});
  for (const row of rows) {
    tbody.append(
      el(
        "tr",
        {},
        el("td", {}, el("b", {}, row.tag)),
        el("td", {}, badge(row.protocol, row.is_wireguard ? "b-accent" : "b-mut")),
        el("td", { class: "mono" }, String(row.port)),
        el(
          "td",
          {},
          switchEl(row.enabled, async (checked) => {
            try {
              const updated = await api.post(`/api/inbounds/${row.id}/enable`, {
                enabled: checked,
              });
              reportApply(updated);
            } catch (err) {
              toast(err.message, "error", 6000);
              rerender(root, inbounds);
            }
          })
        ),
        el("td", {}, `${row.active_clients}/${row.client_count}`),
        el(
          "td",
          { class: "small" },
          `↑ ${fmtBytes(row.up)} · ↓ ${fmtBytes(row.down)}`
        ),
        el(
          "td",
          {},
          el(
            "div",
            { class: "row" },
            el(
              "button",
              {
                class: "btn sm",
                type: "button",
                onclick: () => {
                  location.hash = `#/inbounds/${row.id}`;
                },
              },
              t("btn_details")
            ),
            el(
              "button",
              {
                class: "btn sm",
                type: "button",
                onclick: () => inboundModal(root, row),
              },
              t("btn_edit")
            ),
            el(
              "button",
              {
                class: "btn sm danger",
                type: "button",
                onclick: async () => {
                  if (!(await confirmDialog(t("confirm_delete_msg")))) return;
                  try {
                    const result = await api.del(`/api/inbounds/${row.id}`);
                    toast(t("deleted"), "success");
                    reportApply(result);
                  } catch (err) {
                    toast(err.message, "error", 6000);
                  }
                  rerender(root, inbounds);
                },
              },
              t("btn_delete")
            )
          )
        )
      )
    );
  }
  table.append(tbody);
  holder.append(el("div", { class: "table-wrap" }, table));
}

function inboundModal(root, existing = null) {
  const isEdit = Boolean(existing);
  const current = existing || { params: {} };
  const params = current.params || {};

  const protoSelect = el(
    "select",
    { class: "select" },
    ...PROTOCOLS.map((p) =>
      el(
        "option",
        { value: p, ...(p === (current.protocol || "vless") ? { selected: "selected" } : {}) },
        p
      )
    )
  );
  protoSelect.disabled = isEdit;

  const networkSelect = el(
    "select",
    { class: "select" },
    el("option", { value: "tcp" }, "tcp"),
    el("option", { value: "ws" }, "ws"),
    el("option", { value: "grpc" }, "grpc")
  );
  const securitySelect = el(
    "select",
    { class: "select" },
    el("option", { value: "reality" }, "reality"),
    el("option", { value: "tls" }, "tls"),
    el("option", { value: "none" }, "none")
  );
  const portInput = el("input", {
    class: "input",
    type: "number",
    min: "1",
    max: "65535",
    value: isEdit ? String(current.port) : "",
  });
  portInput.addEventListener("input", () => {
    portInput.dataset.touched = "1";
  });
  const ssSelect = el(
    "select",
    { class: "select" },
    ...SS_METHODS.map((m) =>
      el(
        "option",
        { value: m, ...(m === params.ss_method ? { selected: "selected" } : {}) },
        m
      )
    )
  );
  const sniInput = el("input", {
    class: "input",
    placeholder: "www.samsung.com, www.lovelive-anime.jp",
    value: (params.sni_list || []).join(", "),
  });
  const destInput = el("input", { class: "input", value: params.dest || "" });
  const wsPathInput = el("input", { class: "input", value: params.ws_path || "" });
  const grpcInput = el("input", { class: "input", value: params.grpc_service || "" });
  const flowInput = el("input", {
    class: "input",
    value: params.flow || "",
    placeholder: "xtls-rprx-vision",
  });
  const tagInput = el("input", { class: "input", value: isEdit ? current.tag : "" });
  const listenInput = el("input", {
    class: "input",
    value: current.listen || "0.0.0.0",
  });
  const addrInput = el("input", {
    class: "input",
    value: current.address_override || "",
  });
  const hostInput = el("input", {
    class: "input",
    value: current.host_override || "",
  });
  const sniOvInput = el("input", {
    class: "input",
    value: current.sni_override || "",
  });

  const networkField = field(t("inb_network"), networkSelect);
  const securityField = field(t("inb_security"), securitySelect);
  const ssField = field(t("inb_method"), ssSelect);
  const sniField = field(t("inb_sni"), sniInput);
  const destFieldWrap = field(t("inb_dest"), destInput);
  const wsField = field(t("inb_ws_path"), wsPathInput);
  const grpcField = field(t("inb_grpc_service"), grpcInput);
  const wgHint = el("div", { class: "hint mb" }, t("wg_hint"));

  const updateVisibility = () => {
    const protocol = protoSelect.value;
    const network = networkSelect.value;
    const security = securitySelect.value;

    toggle(networkField, ["vless", "vmess", "trojan"].includes(protocol));
    toggle(securityField, ["vless", "vmess"].includes(protocol));
    toggle(sniField, protocol === "vless" && security === "reality");
    toggle(destFieldWrap, protocol === "vless" && security === "reality");
    toggle(wsField, network === "ws" && protocol !== "wireguard");
    toggle(grpcField, network === "grpc" && protocol !== "wireguard");
    toggle(ssField, protocol === "shadowsocks");
    toggle(wgHint, protocol === "wireguard");
    toggle(advanced, protocol !== "wireguard");

    const allowedNetworks =
      protocol === "vless" ? ["tcp", "ws", "grpc"] : ["tcp", "ws"];
    for (const option of networkSelect.options) {
      option.disabled = !allowedNetworks.includes(option.value);
    }
    const allowedSec =
      protocol === "vless" ? ["reality", "tls", "none"] : ["tls", "none"];
    for (const option of securitySelect.options) {
      option.disabled = !allowedSec.includes(option.value);
    }
  };

  const applyDefaults = () => {
    if (isEdit) return;
    const protocol = protoSelect.value;
    const defaults = {
      vless: { port: 443, network: "tcp", security: "reality" },
      vmess: { port: 8080, network: "ws", security: "none" },
      trojan: { port: 443, network: "tcp", security: "tls" },
      shadowsocks: { port: 8388 },
      wireguard: { port: 51820 },
    }[protocol];
    if (!defaults) return;
    if (!portInput.dataset.touched) portInput.value = String(defaults.port);
    if (defaults.network) networkSelect.value = defaults.network;
    if (defaults.security) securitySelect.value = defaults.security;
  };

  protoSelect.addEventListener("change", () => {
    applyDefaults();
    updateVisibility();
  });
  networkSelect.addEventListener("change", updateVisibility);
  securitySelect.addEventListener("change", updateVisibility);

  if (isEdit && !current.is_wireguard) {
    networkSelect.value = params.network || "tcp";
    securitySelect.value = params.security || "none";
  }

  const advanced = el(
    "details",
    {},
    el("summary", { class: "label", style: "cursor:pointer" }, t("inb_adv")),
    el(
      "div",
      { class: "mt" },
      grid(
        field(t("inb_flow"), flowInput),
        field(t("inb_tag"), tagInput),
        field(t("inb_listen"), listenInput),
        field(t("inb_addr_override"), addrInput),
        field(t("inb_host_override"), hostInput),
        field(t("inb_sni_override"), sniOvInput)
      )
    )
  );

  const body = el(
    "div",
    {},
    grid(
      field(t("inb_protocol"), protoSelect),
      field(t("inb_port"), portInput),
      networkField,
      securityField,
      ssField
    ),
    sniField,
    destFieldWrap,
    wsField,
    grpcField,
    wgHint,
    advanced
  );

  applyDefaults();
  updateVisibility();

  const collect = () => {
    const protocol = protoSelect.value;
    if (protocol === "wireguard") {
      const payload = { protocol: "wireguard", port: num(portInput.value) };
      if (tagInput.value.trim()) payload.tag = tagInput.value.trim();
      return payload;
    }
    const data = {
      protocol,
      port: num(portInput.value),
      listen: listenInput.value.trim() || "0.0.0.0",
      network: networkSelect.value,
      security: securitySelect.value,
      ws_path: wsPathInput.value.trim(),
      grpc_service: grpcInput.value.trim(),
      sni_list: sniInput.value
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean),
      dest: destInput.value.trim(),
      flow: flowInput.value.trim(),
      tag: tagInput.value.trim(),
      address_override: addrInput.value.trim(),
      host_override: hostInput.value.trim(),
      sni_override: sniOvInput.value.trim(),
    };
    if (protocol === "shadowsocks") {
      data.ss_method = ssSelect.value;
      data.network = "tcp";
      data.security = "none";
    }
    if (protocol === "trojan") data.security = "tls";
    return data;
  };

  const save = async () => {
    try {
      const payload = collect();
      if (isEdit) delete payload.protocol;
      const result = isEdit
        ? await api.patch(`/api/inbounds/${current.id}`, payload)
        : await api.post("/api/inbounds", payload);
      reportApply(result);
      if (!(result && result.apply_error)) {
        toast(isEdit ? t("saved") : t("created"), "success");
      }
      modal.close();
      reroute();
    } catch (err) {
      toast(err.message, "error", 7000);
    }
  };

  const modal = openModal({
    title: isEdit ? t("inb_edit_title") : t("inb_create_title"),
    body,
    footer: [
      el("button", { class: "btn primary", type: "button", onclick: save }, t("btn_save")),
      el("button", { class: "btn ghost", type: "button", onclick: () => modal.close() }, t("cancel")),
    ],
  });
}

/* -------------------------- inbound detail ---------------------------- */
export async function inboundDetail(root, idStr) {
  const id = parseInt(idStr, 10);
  root.append(
    pageHeader(`${t("nav_inbounds")} — #${idStr}`, [
      el(
        "button",
        {
          class: "btn",
          type: "button",
          onclick: () => {
            location.hash = "#/inbounds";
          },
        },
        t("btn_back")
      ),
      el(
        "button",
        {
          class: "btn primary",
          type: "button",
          onclick: () => clientModal(root, id),
        },
        t("btn_new_client")
      ),
    ])
  );

  const info = el("div");
  const list = el("div", { class: "mt" });
  root.append(info, list);
  info.append(spinner());

  let row;
  try {
    row = await api.get(`/api/inbounds/${id}`);
  } catch (err) {
    info.innerHTML = "";
    info.append(el("div", { class: "card" }, el("div", { class: "error-text" }, err.message)));
    return;
  }

  info.innerHTML = "";
  const kv = el("div", { class: "kv" });
  const addRow = (key, value, mono = false) =>
    kv.append(
      el("div", { class: "k" }, key),
      el("div", { class: mono ? "mono small" : "small" }, value)
    );

  addRow(t("th_protocol"), `${row.protocol}${row.is_wireguard ? "" : ` · ${row.params.network || "tcp"} · ${row.params.security || "none"}`}`);
  addRow(t("th_port"), String(row.port));
  addRow(t("inb_listen"), row.listen);
  if (!row.is_wireguard) {
    if (row.params.reality_public) {
      kv.append(
        el("div", { class: "k" }, "Reality Public Key"),
        el(
          "div",
          { class: "row" },
          el("span", { class: "mono small" }, row.params.reality_public),
          copyBtn(row.params.reality_public)
        )
      );
    }
    if (row.params.sni_list && row.params.sni_list.length)
      addRow("SNI", row.params.sni_list.join(", "));
    if (row.params.short_ids && row.params.short_ids.length)
      addRow("Short IDs", row.params.short_ids.join(", "), true);
    if (row.params.ws_path) addRow("WS Path", row.params.ws_path, true);
    if (row.params.grpc_service) addRow("gRPC Service", row.params.grpc_service, true);
    if (row.params.ss_method) addRow("Method", row.params.ss_method, true);
  } else {
    addRow("Interface", row.params.iface || "wg0", true);
    if (row.params.server_public) {
      kv.append(
        el("div", { class: "k" }, "Server Public Key"),
        el(
          "div",
          { class: "row" },
          el("span", { class: "mono small" }, row.params.server_public),
          copyBtn(row.params.server_public)
        )
      );
    }
  }
  kv.append(
    el("div", { class: "k" }, t("th_status")),
    el("div", {}, switchEl(row.enabled, async (checked) => {
      try {
        const updated = await api.post(`/api/inbounds/${row.id}/enable`, {
          enabled: checked,
        });
        reportApply(updated);
      } catch (err) {
        toast(err.message, "error", 6000);
      }
    }))
  );

  info.append(card(row.tag, kv));

  await clientsTable(list, { inboundId: id, hostRoot: root });
}

/* ------------------------------ clients ------------------------------- */
export async function clients(root) {
  const inbounds = await api.get("/api/inbounds");
  const filter = el(
    "select",
    { class: "select", style: "max-width:260px" },
    el("option", { value: "" }, t("th_inbound") + ": همه"),
    ...inbounds.map((i) =>
      el("option", { value: String(i.id) }, `${i.tag} (${i.protocol}:${i.port})`)
    )
  );

  root.append(
    pageHeader(t("nav_clients"), [
      el(
        "button",
        { class: "btn", type: "button", onclick: () => rerender(root, clients) },
        t("btn_refresh")
      ),
      el(
        "button",
        { class: "btn primary", type: "button", onclick: () => clientModal(root) },
        t("btn_new_client")
      ),
    ])
  );
  root.append(el("div", { class: "row mb" }, filter));
  const holder = el("div");
  root.append(holder);

  const inboundId = filter.value ? parseInt(filter.value, 10) : null;
  filter.addEventListener("change", () =>
    clientsTable(holder, {
      inboundId: filter.value ? parseInt(filter.value, 10) : null,
      hostRoot: root,
    })
  );
  await clientsTable(holder, { inboundId, hostRoot: root });
}

async function clientsTable(container, { inboundId = null, hostRoot = null } = {}) {
  container.innerHTML = "";
  container.append(spinner());

  const query = inboundId ? `?inbound_id=${inboundId}` : "";
  const rows = await api.get(`/api/clients${query}`);
  container.innerHTML = "";
  if (!rows.length) {
    container.append(emptyCard());
    return;
  }

  const refresh = () => clientsTable(container, { inboundId, hostRoot });

  const table = el("table", { class: "table" });
  table.append(
    el(
      "thead",
      {},
      el(
        "tr",
        {},
        el("th", {}, t("th_name")),
        !inboundId ? el("th", {}, t("th_inbound")) : null,
        el("th", {}, t("th_status")),
        el("th", {}, t("th_usage")),
        el("th", {}, t("th_expiry")),
        el("th", {}, t("th_actions"))
      )
    )
  );

  const tbody = el("tbody", {});
  for (const row of rows) {
    const jalali = row.expiry ? fmtJalali(row.expiry) : "";
    tbody.append(
      el(
        "tr",
        {},
        el("td", {}, el("b", {}, row.name), row.note ? el("div", { class: "small muted" }, row.note) : null),
        !inboundId ? el("td", {}, row.inbound_tag || "—") : null,
        el("td", {}, clientStatusBadge(row)),
        el(
          "td",
          {},
          el(
            "div",
            { class: "small" },
            `${fmtBytes(row.used)} / ${
              row.quota_gb && row.quota_gb > 0
                ? fmtBytes(row.quota_gb * 1024 ** 3)
                : t("client_unlimited")
            }`
          ),
          progressEl(row.used, row.quota_gb || 0)
        ),
        el("td", { class: "small" }, row.expiry ? `${row.expiry}${jalali ? ` (${jalali})` : ""}` : "—"),
        el(
          "td",
          {},
          el(
            "div",
            { class: "row" },
            el(
              "button",
              { class: "btn sm", type: "button", onclick: () => linksModal(row) },
              t("btn_links")
            ),
            el(
              "button",
              { class: "btn sm", type: "button", onclick: () => clientModal(hostRoot, null, row) },
              t("btn_edit")
            ),
            el(
              "button",
              {
                class: "btn sm",
                type: "button",
                onclick: async () => {
                  if (!(await confirmDialog(t("btn_reset_usage") + "؟"))) return;
                  try {
                    await api.post(`/api/clients/${row.id}/reset-usage`);
                    toast(t("saved"), "success");
                  } catch (err) {
                    toast(err.message, "error", 6000);
                  }
                  refresh();
                },
              },
              t("btn_reset_usage")
            ),
            el(
              "button",
              {
                class: "btn sm",
                type: "button",
                onclick: async () => {
                  try {
                    const updated = await api.post(`/api/clients/${row.id}/enable`, {
                      enabled: !row.enabled,
                    });
                    reportApply(updated);
                  } catch (err) {
                    toast(err.message, "error", 6000);
                  }
                  refresh();
                },
              },
              row.enabled ? t("btn_disable") : t("btn_enable")
            ),
            el(
              "button",
              {
                class: "btn sm danger",
                type: "button",
                onclick: async () => {
                  if (!(await confirmDialog(t("confirm_delete_msg")))) return;
                  try {
                    const result = await api.del(`/api/clients/${row.id}`);
                    toast(t("deleted"), "success");
                    reportApply(result);
                  } catch (err) {
                    toast(err.message, "error", 6000);
                  }
                  refresh();
                },
              },
              t("btn_delete")
            )
          )
        )
      )
    );
  }
  table.append(tbody);
  container.append(el("div", { class: "table-wrap" }, table));
}

async function clientModal(root, inboundId = null, existing = null) {
  let inboundSelectEl = null;
  if (!existing) {
    const inbounds = await api.get("/api/inbounds");
    if (!inbounds.length) {
      toast("ابتدا یک اینباند بساز", "warn");
      return;
    }
    if (!inboundId) {
      inboundSelectEl = el(
        "select",
        { class: "select" },
        ...inbounds.map((i) =>
          el("option", { value: String(i.id) }, `${i.tag} (${i.protocol}:${i.port})`)
        )
      );
    }
  }

  const nameInput = el("input", { class: "input", value: existing?.name || "" });
  const quotaInput = el("input", {
    class: "input",
    type: "number",
    min: "0",
    value: existing && existing.quota_gb != null ? String(existing.quota_gb) : "",
  });
  const expiryInput = el("input", {
    class: "input",
    type: "date",
    value: existing?.expiry || "",
  });
  const noteInput = el("input", { class: "input", value: existing?.note || "" });

  const save = async () => {
    try {
      let result;
      if (existing) {
        result = await api.patch(`/api/clients/${existing.id}`, {
          name: nameInput.value.trim(),
          quota_gb: quotaInput.value === "" ? null : num(quotaInput.value),
          expiry: expiryInput.value || null,
          note: noteInput.value.trim(),
        });
      } else {
        result = await api.post("/api/clients", {
          inbound_id: inboundSelectEl
            ? parseInt(inboundSelectEl.value, 10)
            : inboundId,
          name: nameInput.value.trim(),
          quota_gb: quotaInput.value === "" ? null : num(quotaInput.value),
          expiry: expiryInput.value || null,
          note: noteInput.value.trim(),
        });
      }
      reportApply(result);
      toast(existing ? t("saved") : t("created"), "success");
      modal.close();
      reroute();
    } catch (err) {
      toast(err.message, "error", 7000);
    }
  };

  const modal = openModal({
    title: existing ? t("client_edit_title") : t("client_create_title"),
    body: grid(
      inboundSelectEl ? field(t("th_inbound"), inboundSelectEl) : null,
      field(t("client_name"), nameInput),
      field(t("client_quota"), quotaInput),
      field(t("client_expiry"), expiryInput),
      field(t("client_note"), noteInput)
    ),
    footer: [
      el("button", { class: "btn primary", type: "button", onclick: save }, t("btn_save")),
      el("button", { class: "btn ghost", type: "button", onclick: () => modal.close() }, t("cancel")),
    ],
  });
}

async function linksModal(client) {
  const body = el("div");
  const modal = openModal({
    title: `${t("links_title")} — ${client.name}`,
    body,
    wide: true,
  });
  body.append(spinner());

  let data;
  try {
    data = await api.get(`/api/clients/${client.id}/links`);
  } catch (err) {
    body.innerHTML = "";
    body.append(el("div", { class: "error-text" }, err.message));
    return;
  }
  body.innerHTML = "";

  const qrButton = (target) =>
    el(
      "button",
      { class: "btn sm", type: "button", onclick: () => qrModal(client, target) },
      t("btn_qr")
    );

  for (const link of data.links || []) {
    body.append(el("div", { class: "label" }, t("link_label")));
    body.append(
      el(
        "div",
        { class: "link-row" },
        el("input", { class: "input mono code-box", value: link, readonly: "readonly" }),
        copyBtn(link),
        qrButton("link")
      )
    );
  }

  if (data.wg_conf) {
    body.append(el("div", { class: "label" }, t("wg_conf_label")));
    body.append(el("pre", {}, data.wg_conf));
    body.append(
      el("div", { class: "link-row" }, copyBtn(data.wg_conf), qrButton("link"))
    );
  }

  body.append(el("div", { class: "divider" }));
  body.append(el("div", { class: "label" }, t("sub_url")));
  body.append(
    el(
      "div",
      { class: "link-row" },
      el("input", {
        class: "input mono code-box",
        value: data.subscription_url,
        readonly: "readonly",
      }),
      copyBtn(data.subscription_url),
      qrButton("sub")
    )
  );
  body.append(el("div", { class: "hint mt" }, t("insecure_note")));
}

function qrModal(client, target) {
  const image = el("img", {
    class: "qr-img",
    src: `/api/clients/${client.id}/qr.png?target=${target}&_=${Date.now()}`,
    alt: "QR",
  });
  openModal({ title: `${t("btn_qr")} — ${client.name}`, body: el("div", { class: "center" }, image) });
}

/* ------------------------------ settings ------------------------------ */
export async function settings(root) {
  root.append(pageHeader(t("nav_settings"), []));
  const holder = el("div");
  root.append(holder);
  holder.append(spinner());

  const s = await api.get("/api/settings");
  holder.innerHTML = "";

  const savePatch = async (patch) => {
    try {
      const result = await api.patch("/api/settings", { patch });
      if (result.apply && result.apply.ok === false) {
        toast(t("apply_error") + result.apply.message, "warn", 7000);
      } else {
        toast(t("saved"), "success");
      }
    } catch (err) {
      toast(err.message, "error", 7000);
    }
  };

  // Panel
  const panelTitle = el("input", { class: "input", value: s.panel.title || "" });
  const publicHost = el("input", { class: "input", value: s.panel.public_host || "" });
  const subHost = el("input", { class: "input", value: s.subscription.host || "" });
  const subPort = el("input", {
    class: "input",
    type: "number",
    min: "0",
    max: "65535",
    value: String(s.subscription.port || 0),
  });
  holder.append(
    card(
      t("settings_panel_title"),
      grid(
        field(t("settings_panel_name") || "عنوان پنل", panelTitle),
        field(t("settings_public_host"), publicHost),
        field(t("settings_sub_host"), subHost),
        field(t("settings_sub_port"), subPort)
      ),
      el(
        "button",
        {
          class: "btn primary",
          type: "button",
          onclick: () =>
            savePatch({
              panel: { title: panelTitle.value.trim(), public_host: publicHost.value.trim() },
              subscription: { host: subHost.value.trim(), port: num(subPort.value) },
            }),
        },
        t("btn_save")
      )
    )
  );

  // Firewall
  holder.append(
    card(
      t("settings_fw_title"),
      el(
        "div",
        { class: "row between" },
        el("span", {}, t("settings_fw_auto")),
        switchEl(s.firewall.auto_open, (checked) =>
          savePatch({ firewall: { auto_open: checked } })
        )
      )
    )
  );

  // Routing
  const routingCard = card(t("settings_routing_title"));
  const routingRow = (label, key, value) =>
    el(
      "div",
      { class: "row between", style: "padding:4px 0" },
      el("span", {}, label),
      switchEl(value, (checked) => savePatch({ routing: { [key]: checked } }))
    );
  routingCard.append(
    routingRow(t("settings_block25"), "block_port25", s.routing.block_port25),
    routingRow(t("settings_block_private"), "block_private", s.routing.block_private),
    routingRow(t("settings_block_bt"), "block_bittorrent", s.routing.block_bittorrent)
  );
  holder.append(routingCard);

  // WireGuard
  const wgEnabled = s.wireguard.enabled;
  const wgPort = el("input", { class: "input", type: "number", value: String(s.wireguard.port) });
  const wgSubnet = el("input", { class: "input", value: s.wireguard.subnet });
  const wgMtu = el("input", { class: "input", type: "number", value: String(s.wireguard.mtu) });
  const wgDns = el("input", { class: "input", value: s.wireguard.dns });
  const wgWan = el("input", { class: "input", value: s.wireguard.wan_iface || "eth0" });
  holder.append(
    card(
      t("settings_wg_title"),
      el(
        "div",
        { class: "row between mb" },
        el("span", {}, t("settings_wg_enabled")),
        switchEl(wgEnabled, (checked) => savePatch({ wireguard: { enabled: checked } }))
      ),
      grid(
        field(t("settings_wg_port"), wgPort),
        field(t("settings_wg_subnet"), wgSubnet),
        field(t("settings_wg_mtu"), wgMtu),
        field(t("settings_wg_dns"), wgDns),
        field(t("settings_wg_wan"), wgWan)
      ),
      el(
        "button",
        {
          class: "btn primary",
          type: "button",
          onclick: () =>
            savePatch({
              wireguard: {
                port: num(wgPort.value),
                subnet: wgSubnet.value.trim(),
                mtu: num(wgMtu.value),
                dns: wgDns.value.trim(),
                wan_iface: wgWan.value.trim(),
              },
            }),
        },
        t("btn_save")
      )
    )
  );

  // Services
  holder.append(
    card(
      t("settings_services_title"),
      el(
        "div",
        { class: "row" },
        ...["xray", "wg", "panel"].map((name) =>
          el(
            "button",
            {
              class: "btn",
              type: "button",
              onclick: () => restartService(name, root),
            },
            `${t("restart")} ${name}`
          )
        )
      )
    )
  );

  // Certificates
  const certList = el("div", { class: "mb" });
  const domainInput = el("input", { class: "input", placeholder: "sub.example.com" });
  const loadCerts = async () => {
    certList.innerHTML = "";
    try {
      const certs = await api.get("/api/system/certs");
      if (!certs.length) {
        certList.append(el("div", { class: "hint" }, t("settings_cert_none")));
      } else {
        for (const cert of certs) {
          certList.append(el("div", { class: "small mono" }, cert.name));
        }
      }
    } catch (err) {
      certList.append(el("div", { class: "error-text" }, err.message));
    }
  };
  const certCard = card(
    t("settings_certs_title"),
    certList,
    el(
      "div",
      { class: "row" },
      el("div", { style: "flex:1;min-width:200px" }, domainInput),
      el(
        "button",
        {
          class: "btn",
          type: "button",
          onclick: async () => {
            const domain = domainInput.value.trim();
            if (!domain) return;
            try {
              await api.post("/api/system/cert", { domain });
              toast(t("saved"), "success");
              loadCerts();
            } catch (err) {
              toast(err.message, "error", 8000);
            }
          },
        },
        t("settings_cert_issue")
      )
    )
  );
  holder.append(certCard);
  loadCerts();

  // Password
  const oldPw = el("input", { class: "input", type: "password", autocomplete: "current-password" });
  const newPw = el("input", { class: "input", type: "password", autocomplete: "new-password" });
  holder.append(
    card(
      t("settings_pw_title"),
      grid(field(t("settings_pw_old"), oldPw), field(t("settings_pw_new"), newPw)),
      el(
        "button",
        {
          class: "btn primary",
          type: "button",
          onclick: async () => {
            try {
              await api.post("/api/auth/change-password", {
                old_password: oldPw.value,
                new_password: newPw.value,
              });
              toast(t("saved"), "success");
              oldPw.value = "";
              newPw.value = "";
            } catch (err) {
              toast(err.message, "error", 7000);
            }
          },
        },
        t("btn_save")
      )
    )
  );

  // Backup
  holder.append(
    card(
      t("settings_backup_title"),
      el("div", { class: "hint mb" }, t("settings_backup_hint")),
      el(
        "a",
        { class: "btn", href: "/api/system/backup" },
        t("settings_backup_btn")
      )
    )
  );
}

/* -------------------------------- logs -------------------------------- */
export async function logs(root) {
  root.append(
    pageHeader(t("logs_title"), [
      el(
        "button",
        { class: "btn", type: "button", onclick: () => rerender(root, logs) },
        t("btn_refresh")
      ),
    ])
  );
  const holder = el("div");
  root.append(holder);
  holder.append(spinner());

  const rows = await api.get("/api/system/logs?limit=200");
  holder.innerHTML = "";
  if (!rows.length) {
    holder.append(emptyCard());
    return;
  }
  const table = el("table", { class: "table" });
  table.append(
    el(
      "thead",
      {},
      el(
        "tr",
        {},
        el("th", {}, t("th_time")),
        el("th", {}, t("th_actor")),
        el("th", {}, t("th_action")),
        el("th", {}, t("th_detail"))
      )
    )
  );
  const tbody = el("tbody", {});
  for (const row of rows) {
    tbody.append(
      el(
        "tr",
        {},
        el("td", { class: "small" }, `${fmtDate(row.ts)}${fmtJalali(row.ts) ? ` (${fmtJalali(row.ts)})` : ""}`),
        el("td", {}, row.actor || "—"),
        el("td", {}, badge(row.action, "b-mut")),
        el("td", { class: "small" }, row.detail || "")
      )
    );
  }
  table.append(tbody);
  holder.append(el("div", { class: "table-wrap" }, table));
}

/* ------------------------------- about ------------------------------- */
export async function about(root) {
  root.append(pageHeader(t("nav_about"), []));

  const hero = el("div", { class: "about-hero mb" });
  hero.append(
    el("h1", {}, "SMH Panel"),
    el(
      "p",
      { class: "lead" },
      "پنل مدیریت VPN شخصی — ساده برای استفاده، حرفه‌ای در زیرساخت. ساخته شد تا در چند ثانیه اینباند بسازی، کاربر اضافه کنی و لینک / QR تحویل بگیری؛ با نصب تک‌دستوری که خودش امنیت و بهینه‌سازی سرور را هم انجام می‌دهد."
    ),
    el(
      "div",
      { class: "chips" },
      ...[
        "VLESS + Reality",
        "VMess",
        "Trojan",
        "Shadowsocks 2022",
        "WireGuard",
        "لینک اشتراک",
        "سهمیه و انقضا",
        "آمار زنده از Xray",
        "۱۱ پوستهٔ آماده",
        "رابط فارسی RTL",
      ].map((item) => el("span", { class: "chip" }, item))
    )
  );
  root.append(hero);

  const grid = el("div", { class: "grid cards-3 mb" });
  const feat = (title, body) =>
    el(
      "div",
      { class: "card" },
      el("div", { class: "card-title" }, title),
      el("p", { class: "small", style: "margin:0" }, body)
    );
  grid.append(
    feat("چرا SMH Panel؟", "نصب یک‌دستوری که همه‌چیز را خودش تنظیم می‌کند؛ رابط فارسی؛ بدون وابستگی خارجی؛ مناسب برای هر سطحی از تجربه."),
    feat("امنیت", "پنل هرگز root نیست؛ دسترسی ریشه فقط از طریق helperهای اعتبارسنجی‌شده؛ ufw + fail2ban + به‌روزرسانی خودکار امنیتی."),
    feat("کارایی", "پیشنهاد پیش‌فرض VLESS + Reality؛ فعال‌سازی BBR؛ مسیریابی ضد سوءاستفاده؛ خواندن مستقیم آمار از خود Xray.")
  );
  root.append(grid);

  const quotes = el("div", { class: "card mb" });
  quotes.append(el("div", { class: "card-title" }, "چند جمله برای دلگرمی"));
  [
    "«آزادی، آن لحظه شروع می‌شود که بتوانی بدون دغدغه به آنچه می‌خواهی وصل شوی.»",
    "«ابزار خوب، کار بزرگ را ساده می‌کند؛ تو فقط به راه فکر کن.»",
    "«هر سروری که خودت راه می‌اندازی، یک درس تازهٔ مهندسی است.»",
    "«ساده بساز، محکم نگه دار، امن بمان.»",
  ].forEach((q) => quotes.append(el("div", { class: "quote" }, q)));
  root.append(quotes);

  const author = el("div", { class: "card" });
  author.append(el("div", { class: "card-title" }, "سازنده"));
  author.append(
    el(
      "div",
      { class: "author-card" },
      el("div", { class: "avatar" }, "SMH"),
      el(
        "div",
        {},
        el("div", { class: "grad-text", style: "font-size:19px" }, "سید مهدی حسینی"),
        el("div", { class: "muted small" }, "Computer Software Engineer · AI Specialist"),
        el("div", { class: "small" }, "طراحی و توسعهٔ SMH Panel")
      )
    )
  );
  author.append(
    el(
      "div",
      { class: "author-links" },
      el("a", { href: "mailto:dev.smh.ai@gmail.com" }, "📧 dev.smh.ai@gmail.com"),
      el("a", { href: "tel:+989024912785" }, "📱 +98 902 491 2785"),
      el("a", { href: "https://github.com/SMH-AI-Dev/", target: "_blank", rel: "noreferrer" }, "💻 GitHub — SMH-AI-Dev"),
      el("a", { href: "https://huggingface.co/SMH-DEV-AI/", target: "_blank", rel: "noreferrer" }, "🤗 Hugging Face — SMH-DEV-AI")
    )
  );
  author.append(el("div", { class: "divider" }));
  author.append(
    el("div", { class: "small muted" }, `نسخهٔ پنل: ${(state.me && state.me.version) || "—"} · MIT License · github.com/SMH-AI-Dev/smh-vpn-panel`)
  );
  root.append(author);
}

/* --------------------------- theme picker ------------------------------ */
const THEMES = [
  ["dark", "تیره (پیش‌فرض)", ["#0e1116", "#161b23", "#4c8dff"]],
  ["light", "روشن", ["#f3f5f9", "#ffffff", "#2f6fe4"]],
  ["midnight", "نیمه‌شب", ["#0b1020", "#131a33", "#5b8cff"]],
  ["ocean", "اقیانوس", ["#071a20", "#0e2a33", "#22b8cf"]],
  ["forest", "جنگل", ["#0c1512", "#14241c", "#2fbf71"]],
  ["sunset", "غروب", ["#1a0f14", "#2a1720", "#ff7b54"]],
  ["lavender", "یاس", ["#14101f", "#1e1834", "#a78bfa"]],
  ["neon", "نئون", ["#05060a", "#0c1220", "#00e5a0"]],
  ["sand", "شنی", ["#f6f1e7", "#fdfaf3", "#b87333"]],
  ["candy", "پاستیلی", ["#fdf2f6", "#fff9fc", "#e0559a"]],
  ["mono", "خاکستری", ["#f2f3f4", "#fbfbfb", "#3b4450"]],
];

export function openThemePicker() {
  const grid = el("div", { class: "theme-grid" });
  const current = localStorage.getItem("smh_theme") || "dark";
  for (const [key, name, colors] of THEMES) {
    const card = el(
      "div",
      { class: `theme-card${key === current ? " active" : ""}` },
      el(
        "div",
        { class: "theme-swatches" },
        ...colors.map((c) => el("span", { class: "theme-swatch", style: `background:${c}` }))
      ),
      el("div", { class: "theme-name" }, name)
    );
    card.addEventListener("click", () => {
      localStorage.setItem("smh_theme", key);
      document.documentElement.dataset.theme = key;
      grid.querySelectorAll(".theme-card").forEach((n) => n.classList.remove("active"));
      card.classList.add("active");
    });
    grid.append(card);
  }
  openModal({ title: "انتخاب پوسته", body: grid });
}

/* -------------------------------- help -------------------------------- */
export async function help(root) {
  root.append(pageHeader(t("help_title"), []));
  const fa = getLang() === "fa";
  const section = (title, ...children) => card(title, ...children);

  if (fa) {
    root.append(
      section(
        "شروع سریع",
        el("p", {}, "۱) از «اینباندها» یک اینباند بساز. پیشنهاد: VLESS + TCP + Reality روی پورت ۴۴۳ — هم سریع است و هم مقاوم به فیلترینگ."),
        el("p", {}, "۲) از صفحه کاربران، کاربر بساز (نام، سهمیه و تاریخ انقضا اختیاری)."),
        el("p", {}, "۳) روی «لینک و QR» بزن؛ لینک/QR را در اپ کلاینت وارد کن یا لینک اشتراک را بده تا همه کانفیگ‌ها خودکار اضافه شوند."),
        el("p", {}, "۴) برای چند دستگاه، از همان «لینک اشتراک» استفاده کن؛ با هر بار بروزرسانی در اپ، تغییرات اعمال می‌شود.")
      ),
      section(
        "اپ‌های پیشنهادی",
        el("p", {}, "اندروید: v2rayNG یا Hiddify — iOS: Streisand یا FoXray — ویندوز: v2rayN یا Nekoray — مک: FoXray/Nekoray")
      ),
      section(
        "مدیریت مصرف",
        el("p", {}, "وقتی کاربر به سهمیه (GB) یا تاریخ انقضا برسد، خودکار غیرفعال می‌شود. با «ریست ترافیک» شمارنده مصرف صفر می‌شود.")
      ),
      section("گواهی و لینک اشتراک", el("p", {}, t("insecure_note"))),
      section(
        "فایروال و امنیت",
        el("p", {}, "پورت اینباندها هنگام ساخت خودکار در فایروال باز می‌شود (قابل خاموش‌کردن در تنظیمات). نصب‌کننده به‌صورت پیش‌فرض ufw، fail2ban و BBR را فعال می‌کند."),
        el("p", {}, "بلاک پورت ۲۵ و شبکه‌های خصوصی به‌صورت پیش‌فرض فعال است تا سرور برای اسپم/سوءاستفاده بلاک بماند.")
      ),
      section(
        "دستورهای سرور (CLI)",
        el("pre", {}, "smhpanel status\nsmhpanel backup --out /root/backup.tar.gz\nsmhpanel reset-admin-password --user admin\nsystemctl restart smhpanel   # ری‌استارت پنل\njournalctl -u xray -n 100     # لاگ Xray")
      )
    );
  } else {
    root.append(
      section(
        "Quick start",
        el("p", {}, "1) Create an inbound (recommended: VLESS + TCP + Reality on port 443)."),
        el("p", {}, "2) Add clients with optional quota/expiry."),
        el("p", {}, "3) Use “Links & QR” or the subscription URL in your client app."),
        el("p", {}, "4) Recommended apps: v2rayNG, Hiddify, Streisand, v2rayN, Nekoray.")
      ),
      section("Certificates", el("p", {}, t("insecure_note"))),
      section(
        "Server CLI",
        el("pre", {}, "smhpanel status\nsmhpanel backup --out /root/backup.tar.gz\nsystemctl restart smhpanel\njournalctl -u xray -n 100")
      )
    );
  }
}
