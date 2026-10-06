use std::fs;
use std::path::{Path, PathBuf};

use os_linux::read_dropped_file;

/// A fresh directory for one test, named by the test so parallel tests never share one.
fn scratch(name: &str) -> std::io::Result<PathBuf> {
    let dir = std::env::temp_dir().join(format!("cortex-drop-{}-{name}", std::process::id()));
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).map(|()| dir)
}

#[test]
fn a_regular_file_is_read_whole() {
    let dir = scratch("whole").unwrap();
    let path = dir.join("a.png");
    fs::write(&path, b"\x89PNG tea").unwrap();
    assert_eq!(read_dropped_file(&path, 9), Some(b"\x89PNG tea".to_vec()));
    assert_eq!(read_dropped_file(&path, 8), Some(b"\x89PNG tea".to_vec()));
    fs::remove_dir_all(dir).unwrap();
}

#[test]
fn a_file_over_the_limit_is_not_read() {
    let dir = scratch("over").unwrap();
    let path = dir.join("big.png");
    fs::write(&path, [7; 9]).unwrap();
    assert_eq!(read_dropped_file(&path, 8), None);
    fs::remove_dir_all(dir).unwrap();
}

#[test]
fn a_device_is_not_read() {
    assert_eq!(read_dropped_file(Path::new("/dev/zero"), 4), None);
}

#[test]
fn a_directory_or_a_missing_path_is_not_read() {
    let dir = scratch("other").unwrap();
    assert_eq!(read_dropped_file(&dir, usize::MAX), None);
    assert_eq!(read_dropped_file(&dir.join("gone.png"), usize::MAX), None);
    fs::remove_dir_all(dir).unwrap();
}
