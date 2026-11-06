/**
 * Talking to the backend.
 *
 * Inside the Tauri app, requests go through the Rust command `api_get`, which forwards them
 * to the Python backend. In a normal browser (handy for quick UI work, see README) we
 * call the backend directly with fetch().
 */

const BROWSER_BACKEND_URL = "http://127.0.0.1:8000";

const tauri = window.__TAURI__;
export const inTauri = Boolean(tauri?.core?.invoke);

/** GET a backend path such as "/api/v1/portfolio" and return parsed JSON. */
export async function apiGet(path) {
  if (inTauri) {
    return tauri.core.invoke("api_get", { path });
  }
  let res;
  try {
    res = await fetch(BROWSER_BACKEND_URL + path);
  } catch (err) {
    throw new Error(`Cannot reach the uninv backend at ${BROWSER_BACKEND_URL}. Is it running?`);
  }
  if (!res.ok) {
    throw new Error(`Backend returned ${res.status}: ${await res.text()}`);
  }
  return res.json();
}

/** Base URL of the backend (for display only). */
export async function backendUrl() {
  return inTauri ? tauri.core.invoke("backend_url") : BROWSER_BACKEND_URL;
}
