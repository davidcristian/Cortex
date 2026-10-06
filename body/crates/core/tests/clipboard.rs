use body_core::{ClipboardError, ClipboardPicture, MAX_PASTED_BYTES, NoClipboardPicture};

#[test]
fn a_platform_whose_webview_reads_a_paste_has_no_clipboard_picture() {
    assert_eq!(NoClipboardPicture.picture(), Ok(None));
}

#[test]
fn each_refusal_says_why() {
    assert_eq!(
        ClipboardError::TooLarge.to_string(),
        format!("the clipboard's picture is over the {MAX_PASTED_BYTES} byte limit")
    );
    assert_eq!(
        ClipboardError::Failed(String::from("no display")).to_string(),
        "the clipboard could not be read: no display"
    );
}
