/*
 * runtime.rs
 * Exercise actual child ownership and pipe contracts with an isolated fake engine.
 */
use std::{
    fs,
    path::PathBuf,
    sync::{mpsc, Arc},
    thread,
    time::Duration,
};
use transcriber::{Action, Engine, Request, Runtime};

// Keep each runtime independent from user directories and installed model weights.
fn fixture(mode: &str) -> (tempfile::TempDir, Arc<Runtime>) {
    let directory = tempfile::tempdir().unwrap();
    let worker = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../tests/fixtures/worker.py");
    let runtime = Runtime::new(
        Engine {
            program: "python3".into(),
            arguments: vec![worker.to_string_lossy().into_owned(), mode.into()],
        },
        directory.path().join("model cache"),
    )
    .unwrap();
    (directory, Arc::new(runtime))
}

// Model downloading needs no input file, keeping protocol tests inference-free.
fn download() -> Request {
    Request {
        action: Action::Download,
        preset: Some("Medium".into()),
        language: None,
        input: None,
    }
}

// A completed result needs valid identity, a single terminal event and clean exit.
#[test]
fn validates_worker_protocol_and_recovers_after_failures() {
    for (mode, expected) in [
        ("normal", None),
        ("log-flood", None),
        ("wrong-id", Some("identifier mismatch")),
        ("malformed", Some("Invalid worker output")),
        ("duplicate", Some("after its terminal result")),
        ("no-result", Some("without a result")),
        ("crash", Some("Synthetic worker crash")),
    ] {
        let (_directory, runtime) = fixture(mode);
        let result = runtime.perform(download(), |_| {});
        if let Some(expected) = expected {
            assert!(result.unwrap_err().contains(expected), "mode: {mode}");
        } else {
            assert_eq!(result.unwrap()["text"], "Native fixture transcription.");
        }
        // A repeated call must get the same outcome, never a leaked busy reservation.
        assert!(!runtime
            .perform(download(), |_| {})
            .err()
            .unwrap_or_default()
            .contains("already running"));
        runtime.shutdown().unwrap();
    }
}

// Cancellation releases the slot only once the actual long-lived child has exited.
#[test]
fn cancellation_and_shutdown_reap_owned_children() {
    let (_directory, runtime) = fixture("slow");
    let running = runtime.clone();
    let (sender, receiver) = mpsc::channel();
    let operation = thread::spawn(move || {
        running.perform(download(), |_| {
            let _ = sender.send(());
        })
    });
    receiver.recv_timeout(Duration::from_secs(5)).unwrap();
    assert!(runtime
        .perform(download(), |_| {})
        .unwrap_err()
        .contains("already running"));
    runtime.cancel().unwrap();
    assert_eq!(
        operation.join().unwrap().unwrap_err(),
        "Operation cancelled."
    );
    let running = runtime.clone();
    let (sender, receiver) = mpsc::channel();
    let operation = thread::spawn(move || {
        running.perform(download(), |_| {
            let _ = sender.send(());
        })
    });
    receiver.recv_timeout(Duration::from_secs(5)).unwrap();
    runtime.shutdown().unwrap();
    assert_eq!(
        operation.join().unwrap().unwrap_err(),
        "Operation cancelled."
    );
    assert!(runtime.can_exit());
    assert!(runtime
        .perform(download(), |_| {})
        .unwrap_err()
        .contains("closing"));
}

// Invalid media/options fail before the worker starts, including shell-like filenames.
#[test]
fn validates_media_and_preserves_literal_paths() {
    let (directory, runtime) = fixture("normal");
    let path = directory.path().join("recording ' $(touch unsafe).MP3");
    fs::write(&path, b"fixture").unwrap();
    let mut request = Request {
        action: Action::Transcribe,
        preset: Some("Medium".into()),
        language: Some("it".into()),
        input: Some(path),
    };
    assert!(runtime.perform(request.clone(), |_| {}).is_ok());
    assert!(!directory.path().join("unsafe").exists());
    request.language = Some("invalid".into());
    assert!(runtime
        .perform(request.clone(), |_| {})
        .unwrap_err()
        .contains("Italian or English"));
    request.language = Some("en".into());
    request.input = Some(directory.path().join("missing.mp3"));
    assert!(runtime
        .perform(request, |_| {})
        .unwrap_err()
        .contains("existing MP3 or MP4"));
}

// Failed replacements must not truncate previous data or leave temporary siblings.
#[test]
fn exports_utf8_atomically_and_reports_storage_errors() {
    let directory = tempfile::tempdir().unwrap();
    let path = directory.path().join("recording.txt");
    fs::write(&path, "previous").unwrap();
    transcriber::files::save_text(&path, "caffè ☕").unwrap();
    assert_eq!(fs::read_to_string(&path).unwrap(), "caffè ☕\n");
    assert!(
        transcriber::files::save_text(&directory.path().join("missing/result.txt"), "text")
            .is_err()
    );
    assert!(transcriber::files::save_text(&path, "").is_err());
    assert_eq!(fs::read_to_string(&path).unwrap(), "caffè ☕\n");
    assert_eq!(fs::read_dir(directory.path()).unwrap().count(), 1);
}
