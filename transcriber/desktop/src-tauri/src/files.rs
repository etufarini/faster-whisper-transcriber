/*
 * files.rs
 * Replace a TXT export atomically, preserving an existing file on write failures.
 */
use crate::Result;
use std::{io::Write, path::Path};

// Keep the temporary file on the destination filesystem and sync before replacement.
pub fn save_text(path: &Path, text: &str) -> Result<()> {
    if !path.is_absolute() || path.extension().and_then(|value| value.to_str()) != Some("txt") {
        return Err("Choose an absolute TXT destination.".into());
    }
    if text.trim().is_empty() || text.len() > 32 * 1024 * 1024 {
        return Err("The transcription is empty or exceeds the export limit.".into());
    }
    let mut file = tempfile::NamedTempFile::new_in(
        path.parent()
            .ok_or("The destination has no parent directory.")?,
    )
    .map_err(|e| format!("Cannot prepare the export: {e}"))?;
    writeln!(file, "{}", text.trim_end())
        .and_then(|()| file.as_file().sync_all())
        .map_err(|e| format!("Cannot write the export: {e}"))?;
    file.persist(path)
        .map_err(|e| format!("Cannot save the export; previous data was kept: {e}"))?;
    Ok(())
}
