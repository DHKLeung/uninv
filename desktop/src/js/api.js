/**
 * Talking to the backend.
 *
 * Inside the Tauri app, requests go through the Rust command `api_get`, which forwards them
 * to the Python backend. In a normal browser (or mobile web) we call the backend directly with fetch().
 */

const DEFAULT_BACKEND_URL = "http://127.0.0.1:8000";

const tauri = window.__TAURI__;
export const inTauri = Boolean(tauri?.core?.invoke);

/** Get effective backend base URL */
export async function backendUrl() {
  if (inTauri) {
    return tauri.core.invoke("backend_url");
  }
  return localStorage.getItem("uninv_backend_url") || DEFAULT_BACKEND_URL;
}

/** Set backend base URL (for connecting mobile or remote browsers to a host) */
export async function setBackendUrl(url) {
  const clean = url.trim().replace(/\/+$/, "");
  if (inTauri) {
    await tauri.core.invoke("set_backend_url", { url: clean });
  } else {
    localStorage.setItem("uninv_backend_url", clean);
  }
}

/** GET a backend path such as "/api/v1/portfolio" and return parsed JSON. */
export async function apiGet(path) {
  if (inTauri) {
    return tauri.core.invoke("api_get", { path });
  }
  const base = await backendUrl();
  let res;
  try {
    res = await fetch(base + path);
  } catch (err) {
    throw new Error(`Cannot reach the uninv backend at ${base}. Is it running? (${err.message || err})`);
  }
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}: ${await res.text()}`);
  }
  return res.json();
}
