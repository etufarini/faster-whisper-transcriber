/*
 * build.rs
 * Generate Tauri desktop resources only when compiling the native application.
 */

// Runtime-only tests must not require WebKit or desktop configuration generation.
fn main() {
    #[cfg(feature = "desktop")]
    tauri_build::build();
}
