/*
 * process.rs
 * Drain both worker pipes with bounded memory and validate operation identity.
 * The monitor owns/reaps the child on success, failure, cancellation and shutdown.
 */
use crate::{Engine, Result};
use serde_json::Value;
use std::{
    collections::VecDeque,
    io::{BufRead, BufReader, Read, Write},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc, Arc, Mutex,
    },
    thread,
    time::{Duration, Instant},
};

const MAX_MESSAGE: u64 = 32 * 1024 * 1024;
struct OwnedChild(Child);

impl Drop for OwnedChild {
    // Child::drop alone leaves a running process; always terminate and reap our child.
    fn drop(&mut self) {
        if !matches!(self.0.try_wait(), Ok(Some(_))) {
            let _ = self.0.kill();
        }
        let _ = self.0.wait();
    }
}

// Use literal arguments, drain stderr independently, and join readers after reaping.
pub fn execute(
    engine: &Engine,
    request: &Value,
    cancelled: &AtomicBool,
    mut progress: impl FnMut(Value),
) -> Result<Value> {
    let child = Command::new(&engine.program).args(&engine.arguments)
        .env("PYTHONUNBUFFERED", "1").env("HF_HUB_DISABLE_TELEMETRY", "1")
        .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn()
        .map_err(|e| format!("Cannot start the internal Python engine: {e}. Run npm ci during development or reinstall the application."))?;
    let mut child = OwnedChild(child);
    let mut stdin = child
        .0
        .stdin
        .take()
        .ok_or("The worker input pipe is unavailable.")?;
    serde_json::to_writer(&mut stdin, request).map_err(|e| e.to_string())?;
    writeln!(stdin).map_err(|e| e.to_string())?;
    drop(stdin);
    let stdout = child
        .0
        .stdout
        .take()
        .ok_or("The worker output pipe is unavailable.")?;
    let mut stderr = child
        .0
        .stderr
        .take()
        .ok_or("The worker log pipe is unavailable.")?;
    let (sender, receiver) = mpsc::sync_channel(8);
    let output_reader = thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        loop {
            let mut line = Vec::new();
            let result = reader
                .by_ref()
                .take(MAX_MESSAGE + 1)
                .read_until(b'\n', &mut line);
            let message = match result {
                Ok(0) => break,
                Ok(_) if line.len() as u64 > MAX_MESSAGE => {
                    Err("Worker message exceeds the size limit.".into())
                }
                Ok(_) => serde_json::from_slice::<Value>(&line)
                    .map_err(|e| format!("Invalid worker output: {e}")),
                Err(error) => Err(format!("Cannot read worker output: {error}")),
            };
            if sender.send(message).is_err() {
                break;
            }
        }
    });
    let logs = Arc::new(Mutex::new(VecDeque::new()));
    let captured = logs.clone();
    let log_reader = thread::spawn(move || {
        let mut buffer = [0; 4096];
        while let Ok(size) = stderr.read(&mut buffer) {
            if size == 0 {
                break;
            }
            if let Ok(mut bytes) = captured.lock() {
                bytes.extend(&buffer[..size]);
                while bytes.len() > 32768 {
                    bytes.pop_front();
                }
            }
        }
    });
    let result = monitor(&mut child.0, request, cancelled, &receiver, &mut progress);
    // Release backpressure before joining the stdout reader after a protocol failure.
    drop(receiver);
    drop(child);
    let readers = output_reader.join().and(log_reader.join());
    if readers.is_err() {
        return Err("A worker pipe reader failed.".into());
    }
    result.map_err(|error| {
        let bytes: Vec<u8> = logs
            .lock()
            .map(|bytes| bytes.iter().copied().collect())
            .unwrap_or_default();
        let logs = String::from_utf8_lossy(&bytes);
        if logs.trim().is_empty() || error == "Operation cancelled." {
            error
        } else {
            format!("{error}\n{}", logs.trim())
        }
    })
}

// Success requires exactly one result and a successful process exit, not just EOF.
fn monitor(
    child: &mut Child,
    request: &Value,
    cancelled: &AtomicBool,
    receiver: &mpsc::Receiver<Result<Value>>,
    progress: &mut impl FnMut(Value),
) -> Result<Value> {
    let started = Instant::now();
    let mut terminal = None;
    let mut terminal_at = None;
    let mut closed = false;
    loop {
        if cancelled.load(Ordering::Relaxed) {
            return Err("Operation cancelled.".into());
        }
        if request["action"] == "inspect" && started.elapsed() > Duration::from_secs(30) {
            return Err("Model inspection timed out.".into());
        }
        if terminal_at.is_some_and(|time: Instant| time.elapsed() > Duration::from_secs(5)) {
            return Err("The worker did not exit after its result.".into());
        }
        match receiver.recv_timeout(Duration::from_millis(30)) {
            Ok(message) => {
                let message = message?;
                if message["version"] != 1 || message["id"] != request["id"] {
                    return Err("Worker protocol version or operation identifier mismatch.".into());
                }
                if terminal.is_some() {
                    return Err("The worker sent output after its terminal result.".into());
                }
                match message["event"].as_str() {
                    Some("progress") => progress(message),
                    Some("result") => {
                        validate_result(request, &message)?;
                        terminal = Some(message);
                        terminal_at = Some(Instant::now());
                    }
                    Some("error") => {
                        return Err(message["message"]
                            .as_str()
                            .unwrap_or("The worker failed.")
                            .to_owned())
                    }
                    _ => return Err("The worker sent an unknown event.".into()),
                }
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => closed = true,
            Err(mpsc::RecvTimeoutError::Timeout) => {}
        }
        if closed {
            if let Some(exit) = child.try_wait().map_err(|e| e.to_string())? {
                if !exit.success() {
                    return Err(format!("The internal engine exited ({exit})."));
                }
                return terminal
                    .ok_or_else(|| "The internal engine exited without a result.".into());
            }
            thread::sleep(Duration::from_millis(10));
        }
    }
}

// Do not pass incomplete or mistyped terminal data into renderer configuration.
fn validate_result(request: &Value, message: &Value) -> Result<()> {
    let valid = match request["action"].as_str() {
        Some("inspect") => serde_json::from_str::<Value>(crate::PRESETS)
            .map_err(|error| error.to_string())?
            .as_object()
            .is_some_and(|presets| {
                presets
                    .keys()
                    .all(|name| message["models"][name].is_boolean())
            }),
        Some("download") => message["available"] == true,
        Some("transcribe") => message["text"]
            .as_str()
            .is_some_and(|text| !text.trim().is_empty()),
        _ => false,
    };
    if valid {
        Ok(())
    } else {
        Err("The worker returned an incomplete or invalid result.".into())
    }
}
