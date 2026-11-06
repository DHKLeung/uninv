# AGENTS.md: desktop (Tauri 2 + plain JS)

Rules for `desktop/`. Root `AGENTS.md` applies too. **The user doesn't know Rust**, so explain
any Rust change in plain terms.

## Layout
- `src/`: the UI, served as-is (Tauri `frontendDist: "../src"`, no `devUrl`, no build step).
  - `index.html`, `styles.css` (dark theme, CSS variables in `:root`)
  - `js/api.js`: `apiGet(path)`: uses Tauri `invoke("api_get")` inside the app and falls back
    to `fetch("http://127.0.0.1:8000"+path)` in a normal browser. **All backend calls go
    through it.**
  - `js/format.js`: money / pct / qty formatting and `esc()` for HTML escaping.
  - `js/main.js`: loads `/api/v1/portfolio` once, keeps `state`, and renders. Filtering and
    sorting happen in the browser.
- `src-tauri/`: Rust shell.
  - `src/lib.rs`: `Backend` state (reqwest client and base URL from `UNINV_BACKEND_URL`);
    commands `api_get` (generic GET proxy, only `/api/*` and `/health` allowed) and
    `backend_url`.
  - `tauri.conf.json`: window, CSP, bundle and icons. `capabilities/default.json`:
    `core:default` only.
  - `icons/` were generated from `../app-icon.png`; regenerate with
    `cargo tauri icon ../app-icon.png`.

## Conventions
- Tauri **2.x** only (`tauri = "2"`). Tauri 3 is in alpha; don't upgrade.
- No Node.js or bundler unless the user agrees. Use vanilla ES modules, no frameworks, no
  CDN scripts (the CSP blocks them anyway).
- Escape every API-provided string with `esc()` before putting it in `innerHTML`.
- Format numbers with `format.js`. Show base-currency values first and native currency
  second when they differ.
- Add a Rust `#[tauri::command]` only for native features. If you do, register it in
  `generate_handler![...]` and add a permission to `capabilities/` if it uses a plugin.
- `reqwest` is built without TLS (localhost only). Real broker HTTPS calls belong in Python.
- The backend must allow CORS for `http://localhost:1420` / `127.0.0.1:1420` for browser
  mode (`config.py: cors_origins`).
