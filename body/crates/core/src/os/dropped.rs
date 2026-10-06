//! The pictures among the files of a native drop, read only from the paths that drop gave.

use std::path::{Path, PathBuf};
use std::sync::{Mutex, PoisonError};

use super::clipboard::{MAX_PASTED_BYTES, PastedPicture};

/// The absolute paths of the window's last native drop, kept for one read.
#[derive(Debug, Default)]
pub struct DropBox {
    paths: Mutex<Vec<PathBuf>>,
}

impl DropBox {
    /// Replaces the kept paths with the absolute ones among `paths`. A link dropped as a
    /// `text/uri-list` entry arrives as a relative path, so it is never kept.
    pub fn keep(&self, paths: &[PathBuf]) {
        let absolute = paths.iter().filter(|path| path.is_absolute()).cloned();
        *self.paths.lock().unwrap_or_else(PoisonError::into_inner) = absolute.collect();
    }

    /// Takes the kept paths, leaving none for a second read.
    pub fn take(&self) -> Dropped {
        Dropped(std::mem::take(
            &mut *self.paths.lock().unwrap_or_else(PoisonError::into_inner),
        ))
    }
}

/// The paths one drop gave. Only [`DropBox::take`] makes one, so a reader of it never reads a
/// path named anywhere else.
#[derive(Debug, PartialEq, Eq)]
pub struct Dropped(Vec<PathBuf>);

impl Dropped {
    /// The drop's absolute paths, in the order it gave them.
    #[must_use]
    pub fn paths(&self) -> &[PathBuf] {
        &self.0
    }
}

/// The pictures among the files of `dropped`, still encoded. `read` gives at most `limit` bytes
/// of a local file, or `None` when it is not a regular file of that size.
pub fn dropped_pictures(
    dropped: Dropped,
    read: &dyn Fn(&Path, usize) -> Option<Vec<u8>>,
) -> Vec<PastedPicture> {
    let read = dropped
        .0
        .into_iter()
        .filter_map(|path| read(&path, MAX_PASTED_BYTES));
    read.filter_map(|data| picture_type(&data).map(|mime_type| PastedPicture { data, mime_type }))
        .collect()
}

/// The picture type a file's leading bytes name, one of the paste's types, or `None`.
#[must_use]
pub fn picture_type(data: &[u8]) -> Option<&'static str> {
    match data {
        [0x89, b'P', b'N', b'G', b'\r', b'\n', 0x1a, b'\n', ..] => Some("image/png"),
        [0xff, 0xd8, 0xff, ..] => Some("image/jpeg"),
        [b'R', b'I', b'F', b'F', _, _, _, _, kind @ ..] if kind.starts_with(b"WEBP") => {
            Some("image/webp")
        }
        _ => None,
    }
}
