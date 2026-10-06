use std::cell::RefCell;
use std::path::{Path, PathBuf};

use body_core::{DropBox, MAX_PASTED_BYTES, PastedPicture, dropped_pictures, picture_type};

const PNG: &[u8] = &[0x89, b'P', b'N', b'G', b'\r', b'\n', 0x1a, b'\n', 0];
const JPEG: &[u8] = &[0xff, 0xd8, 0xff, 0xe0];
const WEBP: &[u8] = b"RIFF\x10\0\0\0WEBPVP8 ";

fn paths(names: &[&str]) -> Vec<PathBuf> {
    names.iter().map(PathBuf::from).collect()
}

/// Reads from `files` by path and records every path and limit it was asked for.
fn reader<'a>(
    files: &'a [(&'a str, &'a [u8])],
    asked: &'a RefCell<Vec<(PathBuf, usize)>>,
) -> impl Fn(&Path, usize) -> Option<Vec<u8>> + 'a {
    move |path, limit| {
        asked.borrow_mut().push((path.to_path_buf(), limit));
        let found = files.iter().find(|(name, _)| Path::new(name) == path);
        found.map(|(_, data)| data.to_vec())
    }
}

#[test]
fn each_picture_type_is_named_by_its_leading_bytes() {
    assert_eq!(picture_type(PNG), Some("image/png"));
    assert_eq!(picture_type(JPEG), Some("image/jpeg"));
    assert_eq!(picture_type(WEBP), Some("image/webp"));
}

#[test]
fn other_bytes_name_no_picture_type() {
    assert_eq!(picture_type(b"GIF89a"), None);
    assert_eq!(picture_type(b"RIFF\x10\0\0\0WAVEfmt "), None);
    assert_eq!(picture_type(&PNG[..7]), None);
    assert_eq!(picture_type(&[0xff, 0xd8]), None);
    assert_eq!(picture_type(b""), None);
}

#[test]
fn only_the_absolute_paths_of_the_drop_are_read() {
    let drop = DropBox::default();
    let names = [
        "/home/a.png",
        "b.png",
        "http://example.com/c.png",
        "/home/d.txt",
    ];
    drop.keep(&paths(&names));
    let asked = RefCell::new(Vec::new());
    let files: [(&str, &[u8]); 2] = [("/home/a.png", PNG), ("b.png", JPEG)];
    let read = reader(&files, &asked);
    let pictures = dropped_pictures(drop.take(), &read);
    let expected = vec![PastedPicture {
        data: PNG.to_vec(),
        mime_type: "image/png",
    }];
    assert_eq!(pictures, expected);
    let limit = MAX_PASTED_BYTES;
    let wanted = vec![("/home/a.png".into(), limit), ("/home/d.txt".into(), limit)];
    assert_eq!(*asked.borrow(), wanted);
}

#[test]
fn a_drop_is_read_once() {
    let drop = DropBox::default();
    drop.keep(&paths(&["/home/a.png"]));
    let asked = RefCell::new(Vec::new());
    let files: [(&str, &[u8]); 1] = [("/home/a.png", PNG)];
    let read = reader(&files, &asked);
    assert_eq!(dropped_pictures(drop.take(), &read).len(), 1);
    assert_eq!(dropped_pictures(drop.take(), &read), Vec::new());
    assert_eq!(asked.borrow().len(), 1);
}

#[test]
fn a_new_drop_replaces_the_one_before() {
    let drop = DropBox::default();
    drop.keep(&paths(&["/home/a.png", "/home/b.png"]));
    drop.keep(&paths(&["/home/c.webp"]));
    assert_eq!(drop.take().paths(), paths(&["/home/c.webp"]));
    assert_eq!(drop.take().paths(), Vec::<PathBuf>::new());
}

#[test]
fn every_picture_of_a_drop_is_kept_in_order_and_the_rest_left_out() {
    let drop = DropBox::default();
    drop.keep(&paths(&["/w.webp", "/gone.png", "/notes.txt", "/j.jpg"]));
    let asked = RefCell::new(Vec::new());
    let files: [(&str, &[u8]); 3] = [("/w.webp", WEBP), ("/notes.txt", b"tea"), ("/j.jpg", JPEG)];
    let read = reader(&files, &asked);
    let types: Vec<_> = dropped_pictures(drop.take(), &read)
        .into_iter()
        .map(|picture| picture.mime_type)
        .collect();
    assert_eq!(types, ["image/webp", "image/jpeg"]);
}
