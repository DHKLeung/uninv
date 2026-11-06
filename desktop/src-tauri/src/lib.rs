//! uninv desktop app (Rust side).
//!
//! This layer is deliberately thin. The UI lives in `desktop/src` (HTML/JS) and the business
//! logic lives in the Python backend. Rust only does two things:
//!
//! 1. Opens the native window that shows the UI.
//! 2. Exposes a generic `api_get` command that forwards a request to the Python backend.
//!
//! Because of (2), you can add a FastAPI endpoint and call it from JavaScript with
//! `invoke("api_get", { path: "/api/v1/..." })` without changing any Rust.
//!
//! Quick Rust notes for Python developers:
//! - `#[tauri::command]` is like a FastAPI route decorator. It makes the function callable
//!   from JavaScript.
//! - `Result<T, String>` works like "return T or raise an error with this message". On the
//!   JS side an `Err` becomes a rejected promise.
//! - `?` after an expression means "if this failed, return the error right away".
//! - `.map_err(|e| ...)` turns one error type into another (here, into a readable string).

use std::time::Duration;

use serde_json::Value;

/// Default backend address; override with the `UNINV_BACKEND_URL` environment variable.
const DEFAULT_BACKEND_URL: &str = "http://127.0.0.1:8000";

/// Shared state, created once at startup and handed to commands by Tauri
/// (similar to a FastAPI dependency).
struct Backend {
    client: reqwest::Client,
    base_url: String,
}

impl Backend {
    fn from_env() -> Self {
        let base_url = std::env::var("UNINV_BACKEND_URL")
            .unwrap_or_else(|_| DEFAULT_BACKEND_URL.to_string())
            .trim_end_matches('/')
            .to_string();
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(30))
            .no_proxy() // always talk to the local backend directly
            .build()
            .expect("failed to build HTTP client");
        Self { client, base_url }
    }
}

/// GET a JSON endpoint on the Python backend and return the parsed JSON to the UI.
///
/// `path` must be a backend path such as `/api/v1/portfolio` or
/// `/api/v1/positions?group_id=core`. Only `/api/...` and `/health` are allowed, so the UI
/// can't use this command to reach arbitrary URLs.
#[tauri::command]
async fn api_get(path: String, backend: tauri::State<'_, Backend>) -> Result<Value, String> {
    let allowed = (path.starts_with("/api/") || path == "/health") && !path.contains("..");
    if !allowed {
        return Err(format!("Path not allowed: {path}"));
    }

    let url = format!("{}{}", backend.base_url, path);
    let response = backend.client.get(&url).send().await.map_err(|e| {
        format!(
            "Cannot reach the uninv backend at {}. Is it running? ({e})",
            backend.base_url
        )
    })?;

    let status = response.status();
    let body = response.text().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(format!("Backend returned {status}: {body}"));
    }
    serde_json::from_str(&body).map_err(|e| format!("Invalid JSON from backend: {e}"))
}

/// The backend URL in use, so the UI can show it in its status bar.
#[tauri::command]
fn backend_url(backend: tauri::State<'_, Backend>) -> String {
    backend.base_url.clone()
}

/// App entry point, called from `main.rs`.
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(Backend::from_env())
        // Register every command the UI may call here.
        .invoke_handler(tauri::generate_handler![api_get, backend_url])
        .run(tauri::generate_context!())
        .expect("error while running uninv");
}
