/*
 * main.rs
 * Adapt the native window to the testable runtime and resolve the integrated
 * Python engine from source during development or bundled resources in packages.
 */
#[cfg(all(feature = "native-tests", not(debug_assertions)))]
compile_error!("Native automation must not be included in release builds.");

use std::{path::PathBuf, sync::Arc};
use tauri::{ipc::Channel, Emitter, Manager, State};
use transcriber::{Engine, Request, Result, Runtime};

struct Application(Result<Arc<Runtime>>);

// Keep initialization failures visible in the window instead of silently exiting.
fn runtime(state: &State<'_, Application>) -> Result<Arc<Runtime>> {
    state.0.clone()
}

// Inspection shares the worker reservation and cannot overlap a transcription.
#[tauri::command]
async fn inspect_models(state: State<'_, Application>) -> Result<serde_json::Value> {
    let runtime = runtime(&state)?;
    tauri::async_runtime::spawn_blocking(move || runtime.inspect())
        .await
        .map_err(|e| e.to_string())?
}

// Forward one immutable request; progress belongs to this invocation's channel.
#[tauri::command]
async fn perform(
    request: Request,
    events: Channel<serde_json::Value>,
    state: State<'_, Application>,
) -> Result<serde_json::Value> {
    let runtime = runtime(&state)?;
    tauri::async_runtime::spawn_blocking(move || {
        runtime.perform(request, |message| {
            let _ = events.send(message);
        })
    })
    .await
    .map_err(|e| e.to_string())?
}

// Signal the owned operation; the performing thread remains responsible for reaping.
#[tauri::command]
fn cancel_operation(state: State<'_, Application>) -> Result<()> {
    runtime(&state)?.cancel()
}

// Await owned-child cleanup before the renderer destroys the native window.
#[tauri::command]
async fn shutdown(state: State<'_, Application>) -> Result<()> {
    let runtime = runtime(&state)?;
    tauri::async_runtime::spawn_blocking(move || runtime.shutdown())
        .await
        .map_err(|e| e.to_string())?
}

// Atomic writing is kept in the runtime so failures can be checked without a GUI.
#[tauri::command]
async fn save_transcript(path: PathBuf, text: String) -> Result<()> {
    tauri::async_runtime::spawn_blocking(move || transcriber::files::save_text(&path, &text))
        .await
        .map_err(|e| e.to_string())?
}

// Folder opening is explicit and uses literal arguments without a shell.
#[tauri::command]
async fn open_model_folder(state: State<'_, Application>) -> Result<()> {
    let cache = runtime(&state)?.cache.clone();
    tauri::async_runtime::spawn_blocking(move || {
        std::fs::create_dir_all(&cache).map_err(|e| e.to_string())?;
        let program = if cfg!(target_os = "macos") {
            "open"
        } else {
            "xdg-open"
        };
        let status = std::process::Command::new(program)
            .arg(cache)
            .status()
            .map_err(|e| format!("Cannot open the model folder: {e}"))?;
        if status.success() {
            Ok(())
        } else {
            Err("The model folder could not be opened.".into())
        }
    })
    .await
    .map_err(|e| e.to_string())?
}

// Installed builds may only use the bundled engine; source fallback is debug-only.
fn engine(app: &tauri::App) -> Result<Engine> {
    #[cfg(all(feature = "native-tests", debug_assertions))]
    if let Some(worker) = std::env::var_os("TRANSCRIBER_TEST_WORKER") {
        return Ok(Engine {
            program: "python3".into(),
            arguments: vec![worker.to_string_lossy().into_owned()],
        });
    }
    let bundled = app
        .path()
        .resource_dir()
        .map_err(|e| e.to_string())?
        .join("engine/transcriber-engine");
    if bundled.is_file() {
        return Ok(Engine {
            program: bundled,
            arguments: vec![],
        });
    }
    #[cfg(debug_assertions)]
    {
        let directory = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../engine");
        let program = directory.join(".venv/bin/python");
        if !program.is_file() {
            return Err(
                "The internal Python environment is missing. Run npm ci from transcriber/desktop."
                    .into(),
            );
        }
        Ok(Engine {
            program,
            arguments: vec![directory.join("worker.py").to_string_lossy().into_owned()],
        })
    }
    #[cfg(not(debug_assertions))]
    Err("The bundled Python engine is missing. Reinstall the application.".into())
}

// Reuse the old macOS cache in place; other platforms use native application data.
fn cache_directory(app: &tauri::App) -> Result<PathBuf> {
    #[cfg(target_os = "macos")]
    {
        let legacy =
            app.path().home_dir().map_err(|e| e.to_string())?.join(
                "Library/Application Support/faster_whisper_transcriber/models/faster-whisper",
            );
        if legacy.is_dir() {
            return Ok(legacy);
        }
    }
    #[cfg(all(feature = "native-tests", debug_assertions))]
    if let Some(directory) = std::env::var_os("TRANSCRIBER_TEST_CACHE") {
        return Ok(directory.into());
    }
    Ok(app
        .path()
        .app_data_dir()
        .map_err(|e| e.to_string())?
        .join("models/faster-whisper"))
}

// SIGTERM/interrupt cleanup does not depend on renderer callbacks or window focus.
fn watch_signals(handle: tauri::AppHandle, runtime: Arc<Runtime>) {
    tauri::async_runtime::spawn(async move {
        use tokio::signal::unix::{signal, SignalKind};
        let (Ok(mut terminate), Ok(mut interrupt)) = (
            signal(SignalKind::terminate()),
            signal(SignalKind::interrupt()),
        ) else {
            let _ = handle.emit(
                "shutdown-error",
                "Cannot register shutdown signal handlers.",
            );
            return;
        };
        tokio::select! { _ = terminate.recv() => {}, _ = interrupt.recv() => {} }
        let result = tauri::async_runtime::spawn_blocking(move || runtime.shutdown()).await;
        if matches!(result, Ok(Ok(()))) {
            handle.exit(0);
        } else {
            let _ = handle.emit(
                "shutdown-error",
                "The engine could not be stopped during shutdown.",
            );
        }
    });
}

// Register only narrow application commands; automation exists solely in debug tests.
fn main() {
    let context = tauri::generate_context!();
    if std::env::args().nth(1).as_deref() == Some("--check-package") {
        if context.assets().get(&"index.html".into()).is_none() {
            eprintln!("The embedded interface is missing.");
            std::process::exit(1);
        }
        println!("Faster Whisper Transcriber {}", env!("CARGO_PKG_VERSION"));
        return;
    }
    let builder = tauri::Builder::default().plugin(tauri_plugin_dialog::init());
    #[cfg(all(feature = "native-tests", debug_assertions))]
    let builder = builder.plugin(tauri_plugin_wdio_webdriver::init());
    let app = builder
        .setup(|app| {
            let runtime = engine(app)
                .and_then(|engine| Runtime::new(engine, cache_directory(app)?))
                .map(Arc::new);
            if let Ok(runtime) = &runtime {
                watch_signals(app.handle().clone(), runtime.clone());
            }
            app.manage(Application(runtime));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            inspect_models,
            perform,
            cancel_operation,
            shutdown,
            save_transcript,
            open_model_folder
        ])
        .build(context)
        .expect("Could not start Faster Whisper Transcriber");
    app.run(|handle, event| {
        if let tauri::RunEvent::ExitRequested { ref api, .. } = event {
            if let Ok(runtime) = &handle.state::<Application>().0 {
                if !runtime.can_exit() {
                    api.prevent_exit();
                    let _ = handle.emit("close-requested", ());
                }
            }
        }
        if let tauri::RunEvent::Exit = event {
            if let Ok(runtime) = &handle.state::<Application>().0 {
                let _ = runtime.shutdown();
            }
        }
    });
}
