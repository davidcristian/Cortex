//! Reads a file of a native drop for `body_core::dropped_pictures`.

use std::fs::{self, File};
use std::io::Read;
use std::path::Path;

/// At most `limit` bytes of the regular file at `path`, or `None` when it is not one of at most
/// `limit` bytes or cannot be read.
#[must_use]
pub fn read_dropped_file(path: &Path, limit: usize) -> Option<Vec<u8>> {
    let limit = u64::try_from(limit).unwrap_or(u64::MAX);
    let fits = fs::metadata(path).is_ok_and(|found| found.is_file() && found.len() <= limit);
    if !fits {
        return None;
    }
    let mut data = Vec::new();
    let read = File::open(path).and_then(|file| file.take(limit).read_to_end(&mut data));
    read.ok().map(|_| data)
}
