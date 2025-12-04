use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::State;

/// Global state to hold the Python backend process
pub struct PythonBackend {
    pub process: Mutex<Option<Child>>,
}

impl PythonBackend {
    pub fn new() -> Self {
        Self {
            process: Mutex::new(None),
        }
    }
}

#[tauri::command]
pub async fn start_python_backend(state: State<'_, PythonBackend>) -> Result<String, String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    // Check if already running
    if let Some(child) = process_guard.as_mut() {
        if let Ok(None) = child.try_wait() {
            return Err("Python backend is already running".to_string());
        }
    }

    // NOTE: Requires Python 3.10+ installed on the system.
    // This is acceptable for opensource repo where developers have Python.
    // For production app store distributions, see docs/future-enhancements/python-bundling-guide.md

    // Get the backend directory path
    let backend_dir = std::env::current_dir()
        .map_err(|e| e.to_string())?
        .join("backend");

    // Start Python backend using system Python
    let child = Command::new("python")
        .arg("main.py")
        .current_dir(&backend_dir)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start Python backend: {}", e))?;

    *process_guard = Some(child);

    Ok("Python backend started successfully".to_string())
}

#[tauri::command]
pub async fn stop_python_backend(state: State<'_, PythonBackend>) -> Result<String, String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    if let Some(mut child) = process_guard.take() {
        child
            .kill()
            .map_err(|e| format!("Failed to kill Python process: {}", e))?;
        child
            .wait()
            .map_err(|e| format!("Failed to wait for Python process: {}", e))?;

        Ok("Python backend stopped successfully".to_string())
    } else {
        Err("Python backend is not running".to_string())
    }
}

#[tauri::command]
pub async fn is_backend_running(state: State<'_, PythonBackend>) -> Result<bool, String> {
    let mut process_guard = state.process.lock().map_err(|e| e.to_string())?;

    if let Some(child) = process_guard.as_mut() {
        match child.try_wait() {
            Ok(None) => Ok(true),  // Process is still running
            Ok(Some(_)) => {
                *process_guard = None;
                Ok(false)  // Process has exited
            }
            Err(e) => Err(format!("Error checking process status: {}", e)),
        }
    } else {
        Ok(false)
    }
}

#[tauri::command]
pub async fn check_backend_health() -> Result<String, String> {
    // Make HTTP request to backend health endpoint
    let client = reqwest::Client::new();

    match client
        .get("http://127.0.0.1:8765/health")
        .timeout(std::time::Duration::from_secs(5))
        .send()
        .await
    {
        Ok(response) => {
            if response.status().is_success() {
                Ok("Backend is healthy".to_string())
            } else {
                Err(format!("Backend returned status: {}", response.status()))
            }
        }
        Err(e) => Err(format!("Failed to connect to backend: {}", e)),
    }
}

#[tauri::command]
pub fn get_backend_url() -> String {
    "http://127.0.0.1:8765".to_string()
}
