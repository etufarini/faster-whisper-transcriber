/*
 * lib.rs
 * Validate requests and own one short-lived Python worker at a time. Cancellation
 * retains the child until reaping; terminal protocol output alone never frees it.
 */
pub mod files;
mod process;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    path::PathBuf,
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        Arc, Condvar, Mutex,
    },
    time::Duration,
};

pub type Result<T> = std::result::Result<T, String>;
pub const PRESETS: &str = include_str!("../../../engine/presets.json");

#[derive(Clone)]
pub struct Engine {
    pub program: PathBuf,
    pub arguments: Vec<String>,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Action {
    Inspect,
    Download,
    Transcribe,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Request {
    pub action: Action,
    pub preset: Option<String>,
    pub language: Option<String>,
    pub input: Option<PathBuf>,
}

struct Job {
    id: u64,
    cancelled: Arc<AtomicBool>,
}
#[derive(Default)]
struct State {
    job: Option<Job>,
    closing: bool,
}

pub struct Runtime {
    engine: Engine,
    pub cache: PathBuf,
    state: Mutex<State>,
    idle: Condvar,
    sequence: AtomicU64,
}

struct Operation<'a> {
    runtime: &'a Runtime,
    id: u64,
}

impl Drop for Operation<'_> {
    // Clear the reservation only after the owned worker and readers have finished.
    fn drop(&mut self) {
        if let Ok(mut state) = self.runtime.state.lock() {
            if state.job.as_ref().is_some_and(|job| job.id == self.id) {
                state.job = None;
                self.runtime.idle.notify_all();
            }
        }
    }
}

impl Runtime {
    // Construction does not create user directories or start an inference process.
    pub fn new(engine: Engine, cache: PathBuf) -> Result<Self> {
        if !cache.is_absolute() {
            return Err("The model cache must be an absolute path.".into());
        }
        Ok(Self {
            engine,
            cache,
            state: Mutex::new(State::default()),
            idle: Condvar::new(),
            sequence: AtomicU64::new(1),
        })
    }

    // Validate once before reserving the single operation slot or spawning a child.
    pub fn perform(&self, request: Request, progress: impl FnMut(Value)) -> Result<Value> {
        self.validate(&request)?;
        let id = self.sequence.fetch_add(1, Ordering::Relaxed);
        let cancelled = Arc::new(AtomicBool::new(false));
        {
            let mut state = self.state.lock().map_err(|e| e.to_string())?;
            if state.closing {
                return Err("The application is closing.".into());
            }
            if state.job.is_some() {
                return Err("Another operation is already running.".into());
            }
            state.job = Some(Job {
                id,
                cancelled: cancelled.clone(),
            });
        }
        let _operation = Operation { runtime: self, id };
        let mut envelope = serde_json::to_value(&request).map_err(|e| e.to_string())?;
        envelope["version"] = json!(1);
        envelope["id"] = json!(id);
        envelope["cacheDir"] = json!(self.cache);
        process::execute(&self.engine, &envelope, &cancelled, progress)
    }

    // Inspect through the same engine boundary, returning the single preset definition.
    pub fn inspect(&self) -> Result<Value> {
        let result = self.perform(
            Request {
                action: Action::Inspect,
                preset: None,
                language: None,
                input: None,
            },
            |_| {},
        )?;
        Ok(
            json!({ "models": result["models"], "presets": serde_json::from_str::<Value>(PRESETS).map_err(|e| e.to_string())?, "cacheDir": self.cache }),
        )
    }

    // Request cancellation without relinquishing ownership or admitting another job.
    pub fn cancel(&self) -> Result<()> {
        let state = self.state.lock().map_err(|e| e.to_string())?;
        if let Some(job) = &state.job {
            job.cancelled.store(true, Ordering::Relaxed);
        }
        Ok(())
    }

    // Prevent further starts and wait for the operation thread to reap its child.
    pub fn shutdown(&self) -> Result<()> {
        let mut state = self.state.lock().map_err(|e| e.to_string())?;
        state.closing = true;
        if let Some(job) = &state.job {
            job.cancelled.store(true, Ordering::Relaxed);
        }
        let (state, _) = self
            .idle
            .wait_timeout_while(state, Duration::from_secs(10), |state| state.job.is_some())
            .map_err(|e| e.to_string())?;
        if state.job.is_some() {
            return Err("The worker has not stopped. The application will remain open.".into());
        }
        Ok(())
    }

    // Native menu exits may bypass window close events; require completed shutdown.
    pub fn can_exit(&self) -> bool {
        self.state
            .lock()
            .is_ok_and(|state| state.closing && state.job.is_none())
    }

    // Reject invalid options at the native boundary even if the renderer is bypassed.
    fn validate(&self, request: &Request) -> Result<()> {
        if matches!(request.action, Action::Inspect) {
            return Ok(());
        }
        let presets: Value = serde_json::from_str(PRESETS).map_err(|e| e.to_string())?;
        if request
            .preset
            .as_ref()
            .is_none_or(|name| presets.get(name).is_none())
        {
            return Err("Choose a valid transcription preset.".into());
        }
        if matches!(request.action, Action::Transcribe) {
            if !matches!(request.language.as_deref(), Some("it" | "en")) {
                return Err("Choose Italian or English.".into());
            }
            let path = request.input.as_ref().ok_or("Choose an MP3 or MP4 file.")?;
            let extension = path
                .extension()
                .and_then(|value| value.to_str())
                .unwrap_or("")
                .to_ascii_lowercase();
            if !path.is_absolute()
                || !path.is_file()
                || !matches!(extension.as_str(), "mp3" | "mp4")
            {
                return Err("Choose an existing MP3 or MP4 file.".into());
            }
            std::fs::File::open(path).map_err(|e| format!("Cannot read the selected file: {e}"))?;
        }
        Ok(())
    }
}
