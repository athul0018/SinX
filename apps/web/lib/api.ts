const API = process.env.NEXT_PUBLIC_API_URL || "";

const TOKEN_KEY = "gsb_token";
const SITE_KEY = "gsb_site";

export type Site = { id: string; name: string; code: string; status: string };

export type User = {
  id: string;
  name: string;
  email: string;
  global_role: "OWNER" | "AUTHORIZED";
  is_active: boolean;
  sites: Site[];
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function getSiteId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(SITE_KEY) || sessionStorage.getItem(SITE_KEY);
}

export function setSiteId(id: string) {
  localStorage.setItem(SITE_KEY, id);
  sessionStorage.setItem(SITE_KEY, id);
}

function errorMessage(data: unknown, fallback: string) {
  if (!data || typeof data !== "object") return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => (typeof item === "object" && item && "msg" in item ? String((item as { msg: string }).msg) : String(item))).join("; ");
  }
  return fallback;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const isForm = typeof FormData !== "undefined" && init.body instanceof FormData;
  if (!headers.has("Content-Type") && init.body && !isForm) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (res.status === 401) {
    let detail = "Invalid email or password";
    try {
      const data = await res.json();
      detail = errorMessage(data, path.includes("/auth/login") ? "Invalid email or password" : "Not authenticated");
    } catch {
      detail = path.includes("/auth/login") ? "Invalid email or password" : "Not authenticated";
    }
    if (!path.includes("/auth/login")) {
      clearToken();
      if (typeof window !== "undefined") window.location.href = "/login";
    }
    throw new Error(detail);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      detail = errorMessage(data, detail);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export function login(email: string, password: string) {
  return api<{ token: string; user: User }>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function me() {
  return api<User>("/api/v1/auth/me");
}

export async function downloadExcel(path: string, filename: string) {
  const res = await fetch(`${API}${path}`, {
    headers: { Authorization: `Bearer ${getToken() || ""}` },
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error("Download failed");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
