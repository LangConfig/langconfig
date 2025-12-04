mod python_backend;

use python_backend::PythonBackend;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(PythonBackend::new())
        .invoke_handler(tauri::generate_handler![
            python_backend::start_python_backend,
            python_backend::stop_python_backend,
            python_backend::is_backend_running,
            python_backend::check_backend_health,
            python_backend::get_backend_url,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
