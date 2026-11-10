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

use std::net::{SocketAddr, TcpStream};
use std::sync::{Arc, Mutex, RwLock};
use std::time::Duration;

use serde_json::Value;
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;

/// Default backend address; override with the `UNINV_BACKEND_URL` environment variable.
const DEFAULT_BACKEND_URL: &str = "http://127.0.0.1:7541";

/// Check if the backend is already listening on 127.0.0.1:7541.
fn is_backend_listening() -> bool {
    let addr: Result<SocketAddr, _> = "127.0.0.1:7541".parse();
    if let Ok(addr) = addr {
        TcpStream::connect_timeout(&addr, Duration::from_millis(200)).is_ok()
    } else {
        false
    }
}

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

/// Open an external URL in the default web browser (similar to Python's `webbrowser.open(url)`).
#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
    if !url.starts_with("http://") && !url.starts_with("https://") {
        return Err("Invalid URL: must start with http:// or https://".to_string());
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        std::process::Command::new("cmd")
            .args(["/c", "start", "", &url])
            .creation_flags(CREATE_NO_WINDOW)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(&url)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(&url)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Forcefully terminates a process and all of its spawned child processes (process tree).
/// On Windows, PyInstaller --onefile runs as a bootloader that spawns a child Python process.
/// Standard child.kill() only kills the bootloader, leaving the child listening on port 7541.
/// `taskkill /F /T` terminates the entire tree.
fn kill_process_tree(pid: u32) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        let _ = std::process::Command::new("taskkill")
            .args(["/F", "/T", "/PID", &pid.to_string()])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
    }
    #[cfg(not(windows))]
    {
        let _ = std::process::Command::new("pkill")
            .args(["-P", &pid.to_string()])
            .output();
    }
}

/// Safely terminates the sidecar child and cleans up its process tree.
fn terminate_sidecar(sidecar_child: &Arc<Mutex<Option<CommandChild>>>) {
    if let Some(child) = sidecar_child.lock().unwrap().take() {
        let pid = child.pid();
        eprintln!("[uninv] Terminating sidecar process tree (PID {pid}) on app exit");
        kill_process_tree(pid);
        let _ = child.kill();
    }
}

#[cfg(windows)]
mod win_job {
    use std::mem::size_of;
    use std::ptr::null_mut;

    type HANDLE = *mut std::ffi::c_void;
    type BOOL = i32;
    type DWORD = u32;

    const JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: DWORD = 0x2000;
    const JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: i32 = 9;
    const PROCESS_SET_QUOTA: DWORD = 0x0100;
    const PROCESS_TERMINATE: DWORD = 0x0001;

    #[repr(C)]
    struct IO_COUNTERS {
        read_operation_count: u64,
        write_operation_count: u64,
        other_operation_count: u64,
        read_transfer_count: u64,
        write_transfer_count: u64,
        other_transfer_count: u64,
    }

    #[repr(C)]
    struct JOBOBJECT_BASIC_LIMIT_INFORMATION {
        per_process_user_time_limit: i64,
        per_job_user_time_limit: i64,
        limit_flags: DWORD,
        minimum_working_set_size: usize,
        maximum_working_set_size: usize,
        active_process_limit: DWORD,
        affinity: usize,
        priority_class: DWORD,
        scheduling_class: DWORD,
    }

    #[repr(C)]
    struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION {
        basic_limit_information: JOBOBJECT_BASIC_LIMIT_INFORMATION,
        io_info: IO_COUNTERS,
        process_memory_limit: usize,
        job_memory_limit: usize,
        peak_process_memory_used: usize,
        peak_job_memory_used: usize,
    }

    extern "system" {
        fn CreateJobObjectW(lpJobAttributes: *mut std::ffi::c_void, lpName: *const u16) -> HANDLE;
        fn SetInformationJobObject(
            hJob: HANDLE,
            JobObjectInformationClass: i32,
            lpJobObjectInformation: *mut std::ffi::c_void,
            cbJobObjectInformationLength: DWORD,
        ) -> BOOL;
        fn AssignProcessToJobObject(hJob: HANDLE, hProcess: HANDLE) -> BOOL;
        fn OpenProcess(dwDesiredAccess: DWORD, bInheritHandle: BOOL, dwProcessId: DWORD) -> HANDLE;
        fn CloseHandle(hObject: HANDLE) -> BOOL;
    }

    /// Windows Job Object wrapper (comparable to Python's win32job in pywin32).
    /// When the JobObject handle closes or the parent process terminates (even unexpectedly),
    /// the Windows kernel automatically terminates all processes in the job object.
    pub struct JobObject(HANDLE);
    unsafe impl Send for JobObject {}
    unsafe impl Sync for JobObject {}

    impl JobObject {
        pub fn create_kill_on_close() -> Option<Self> {
            unsafe {
                let job = CreateJobObjectW(null_mut(), null_mut());
                if job.is_null() {
                    return None;
                }
                let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
                info.basic_limit_information.limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                let ok = SetInformationJobObject(
                    job,
                    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                    &mut info as *mut _ as *mut std::ffi::c_void,
                    size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as DWORD,
                );
                if ok == 0 {
                    CloseHandle(job);
                    return None;
                }
                Some(JobObject(job))
            }
        }

        pub fn assign_process(&self, pid: u32) -> bool {
            unsafe {
                let proc_handle = OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, 0, pid);
                if proc_handle.is_null() {
                    return false;
                }
                let ok = AssignProcessToJobObject(self.0, proc_handle);
                CloseHandle(proc_handle);
                ok != 0
            }
        }
    }

    impl Drop for JobObject {
        fn drop(&mut self) {
            unsafe {
                if !self.0.is_null() {
                    CloseHandle(self.0);
                }
            }
        }
    }
}

/// App entry point, called from `main.rs` (or mobile runtime).
#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let sidecar_child: Arc<Mutex<Option<CommandChild>>> = Arc::new(Mutex::new(None));
    let sidecar_child_setup = sidecar_child.clone();
    let sidecar_child_win = sidecar_child.clone();
    let sidecar_child_exit = sidecar_child.clone();

    #[cfg(windows)]
    let job_object_holder: Arc<Mutex<Option<win_job::JobObject>>> = Arc::new(Mutex::new(None));
    #[cfg(windows)]
    let job_object_setup = job_object_holder.clone();

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(Backend::from_env())
        .setup(move |app| {
            // If backend is already running (e.g. dev mode), do not start another instance
            if !is_backend_listening() {
                let current_pid = std::process::id();
                match app.shell().sidecar("uninv-backend") {
                    Ok(command) => {
                        let command = command.args(["--parent-pid", &current_pid.to_string()]);
                        match command.spawn() {
                            Ok((_rx, child)) => {
                                let pid = child.pid();
                                eprintln!("[uninv] Spawned Python backend sidecar (PID {pid}) with parent PID {current_pid}");

                                #[cfg(windows)]
                                {
                                    if let Some(job) = win_job::JobObject::create_kill_on_close() {
                                        if job.assign_process(pid) {
                                            eprintln!("[uninv] Assigned sidecar PID {pid} to Windows Job Object (KILL_ON_JOB_CLOSE)");
                                            *job_object_setup.lock().unwrap() = Some(job);
                                        }
                                    }
                                }

                                *sidecar_child_setup.lock().unwrap() = Some(child);

                                // Poll until backend is ready (up to 15s)
                                for _ in 0..30 {
                                    std::thread::sleep(Duration::from_millis(500));
                                    if is_backend_listening() {
                                        eprintln!("[uninv] Python backend is listening on port 7541");
                                        std::thread::sleep(Duration::from_millis(200));
                                        break;
                                    }
                                }
                            }
                            Err(e) => {
                                eprintln!("[uninv] Failed to spawn sidecar: {e}");
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!("[uninv] Sidecar not found or not configured: {e}");
                    }
                }
            } else {
                eprintln!("[uninv] Backend already listening on port 7541");
            }
            Ok(())
        })
        .on_window_event(move |_window, event| {
            match event {
                tauri::WindowEvent::CloseRequested { .. } | tauri::WindowEvent::Destroyed => {
                    terminate_sidecar(&sidecar_child_win);
                }
                _ => {}
            }
        })
        .invoke_handler(tauri::generate_handler![
            api_get,
            api_post,
            backend_url,
            set_backend_url,
            open_url
        ])
        .build(tauri::generate_context!())
        .expect("error while building uninv");

    app.run(move |_app_handle, event| {
        if let tauri::RunEvent::ExitRequested { .. } | tauri::RunEvent::Exit = event {
            terminate_sidecar(&sidecar_child_exit);
        }
    });
}
