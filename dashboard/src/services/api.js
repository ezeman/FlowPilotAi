let authToken = null;
let activeAccountId = null;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export function setAuthToken(token) {
  authToken = token;
}

export function setActiveAccountId(accountId) {
  activeAccountId = accountId ? String(accountId) : null;
}

export async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }
  if (activeAccountId) {
    headers.set("X-Account-Id", activeAccountId);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    let message = "Request failed";
    try {
      const payload = await response.json();
      const detail = payload.detail ?? payload.message;
      const lang = localStorage.getItem("fp_lang") || "th";
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        message = detail.map((e) => e.msg ?? JSON.stringify(e)).join(", ");
      } else if (detail && typeof detail === "object") {
        message = detail[lang] || detail.en || detail.th || JSON.stringify(detail);
      }
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}
