/* Tiny fetch wrapper with cookie session + CSRF double-submit. */
let csrf =
  (typeof localStorage !== "undefined" && localStorage.getItem("smh_csrf")) || "";

export function setCsrf(value) {
  csrf = value || "";
  try {
    if (value) localStorage.setItem("smh_csrf", value);
    else localStorage.removeItem("smh_csrf");
  } catch (err) {
    /* private mode: keep in memory only */
  }
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(method, path, body) {
  const options = { method, headers: {}, credentials: "same-origin" };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  if (!["GET", "HEAD"].includes(method) && csrf) {
    options.headers["X-CSRF-Token"] = csrf;
  }

  let response;
  try {
    response = await fetch(path, options);
  } catch (err) {
    throw new ApiError("network error", 0);
  }

  if (response.status === 401) {
    setCsrf("");
    throw new ApiError("unauthorized", 401);
  }

  const contentType = response.headers.get("content-type") || "";
  let data = null;
  if (contentType.includes("application/json")) {
    data = await response.json().catch(() => null);
  }

  if (!response.ok) {
    let message =
      (data && (data.detail || data.message)) || response.statusText || "error";
    if (typeof message !== "string") message = JSON.stringify(message);
    throw new ApiError(message, response.status);
  }
  return data;
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body === undefined ? {} : body),
  patch: (path, body) => request("PATCH", path, body === undefined ? {} : body),
  del: (path) => request("DELETE", path),
  async login(username, password) {
    const result = await request("POST", "/api/auth/login", { username, password });
    setCsrf(result.csrf_token);
    return result;
  },
  async logout() {
    try {
      await request("POST", "/api/auth/logout");
    } finally {
      setCsrf("");
    }
  },
};
