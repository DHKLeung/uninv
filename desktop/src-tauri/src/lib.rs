//! uninv desktop & mobile app (Rust side).
//!
//! This layer is deliberately thin and cross-platform (Windows, macOS, Linux, iOS).
//! The UI lives in `desktop/src` (HTML/JS) and the business logic lives in the Python backend.
//! Rust handles:
//!
//! 1. Opening the native window (or mobile webview).
//! 2. Exposing generic `api_get` and `set_backend_url` commands that bridge the UI to the backend.
//!
//! On desktop (Windows/macOS/Linux), the Python backend can run locally (e.g. sidecar).
//! On mobile (iOS), the app connects over the network to the user's backend server.
//!
//! Quick Rust notes for Python developers:
//! - `#[tauri::command]` is like a FastAPI route decorator. It makes the function callable
//!   from JavaScript.
//! - `Result<T, String>` works like "return T or raise an error with this message". On the
//!   JS side an `Err` becomes a rejected promise.
//! - `?` after an expression means "if this failed, return the error right away".
//! - `.map_err(|e| ...)` turns one error type into another (here, into a readable string).

use std::sync::RwLock;
use std::time::Duration;

use serde_json::Value;

/// Default backend address; override with the `UNINV_BACKEND_URL` environment variable.
const DEFAULT_BACKEND_URL: &str = "http://127.0.0.1:8000";

/// Shared state, created once at startup and handed to commands by Tauri.
struct Backend {
    client: reqwest::Client,
    base_url: RwLock<String>,
}

impl Backend {
    fn from_env() -> Self {
        let base_url = std::env::var("UNINV_BACKEND_URL")
            .unwrap_or_else(|_| DEFAULT_BACKEND_URL.to_string())
            .trim_end_matches('/')
            .to_string();
        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("failed to build HTTP client");
        Self {
            client,
            base_url: RwLock::new(base_url),
        }
    }
}

/// GET a JSON endpoint on the Python backend and return the parsed JSON to the UI.
///
/// `path` must be a backend path such as `/api/v1/portfolio` or
/// `/api/v1/positions?group_id=core`. Only `/api/...` and `/health` are allowed.
#[tauri::command]
async fn api_get(path: String, backend: tauri::State<'_, Backend>) -> Result<Value, String> {
    let allowed = (path.starts_with("/api/") || path == "/health") && !path.contains("..");
    if !allowed {
        return Err(format!("Path not allowed: {path}"));
    }

    let base_url = backend
        .base_url
        .read()
        .map_err(|e| e.to_string())?
        .clone();
    let url = format!("{}{}", base_url, path);
    let response = backend.client.get(&url).send().await.map_err(|e| {
        format!(
            "Cannot reach the uninv backend at {}. Is it running? ({e})",
            base_url
        )
    })?;

    let status = response.status();
    let body = response.text().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(format!("Backend returned {status}: {body}"));
    }
    serde_json::from_str(&body).map_err(|e| format!("Invalid JSON from backend: {e}"))
}

/// POST a JSON payload to a Python backend endpoint and return parsed JSON.
/// Similar to Python's requests.post(url, json=body).
#[tauri::command]
async fn api_post(
    path: String,
    body: Value,
    backend: tauri::State<'_, Backend>,
) -> Result<Value, String> {
    let allowed = path.starts_with("/api/") && !path.contains("..");
    if !allowed {
        return Err(format!("Path not allowed: {path}"));
    }

    let base_url = backend
        .base_url
        .read()
        .map_err(|e| e.to_string())?
        .clone();
    let url = format!("{}{}", base_url, path);
    let response = backend
        .client
        .post(&url)
        .json(&body)
        .send()
        .await
        .map_err(|e| {
            format!(
                "Cannot reach the uninv backend at {}. Is it running? ({e})",
                base_url
            )
        })?;

    let status = response.status();
    let res_body = response.text().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(format!("Backend returned {status}: {res_body}"));
    }
    serde_json::from_str(&res_body).map_err(|e| format!("Invalid JSON from backend: {e}"))
}

/// The backend URL in use, so the UI can show it in its status bar.
#[tauri::command]
fn backend_url(backend: tauri::State<'_, Backend>) -> Result<String, String> {
    backend
        .base_url
        .read()
        .map(|guard| guard.clone())
        .map_err(|e| e.to_string())
}

/// Dynamically update the backend URL (essential for iOS connecting to a host machine or remote server).
#[tauri::command]
fn set_backend_url(url: String, backend: tauri::State<'_, Backend>) -> Result<(), String> {
    let clean = url.trim().trim_end_matches('/').to_string();
    if clean.is_empty() || (!clean.starts_with("http://") && !clean.starts_with("https://")) {
        return Err("Backend URL must start with http:// or https://".to_string());
    }
    let mut guard = backend.base_url.write().map_err(|e| e.to_string())?;
    *guard = clean;
    Ok(())
}

/// App entry point, called from `main.rs` (or mobile runtime).
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(Backend::from_env())
        // Register every command the UI may call here.
        .invoke_handler(tauri::generate_handler![
            api_get,
            api_post,
            backend_url,
            set_backend_url
        ])
        .run(tauri::generate_context!())
        .expect("error while running uninv");
}
