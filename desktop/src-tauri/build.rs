use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    // If the external sidecar binary doesn't exist yet (e.g. in CI or dev cargo check),
    // create a placeholder dummy file so tauri-build doesn't panic.
    let target = env::var("TARGET").unwrap_or_default();
    if !target.is_empty() {
        let ext = if target.contains("windows") { ".exe" } else { "" };
        let binaries_dir = PathBuf::from("binaries");
        let _ = fs::create_dir_all(&binaries_dir);
        let sidecar_name = format!("uninv-backend-{target}{ext}");
        let sidecar_path = binaries_dir.join(sidecar_name);
        if !sidecar_path.exists() {
            let _ = fs::write(&sidecar_path, b"");
        }
    }

    // Generates Tauri's build-time glue (config, icons, permissions). Leave as is.
    tauri_build::build()
}
