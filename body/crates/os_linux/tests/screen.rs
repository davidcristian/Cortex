#![cfg(target_os = "linux")]

use std::sync::{Arc, Mutex, PoisonError};

use body_core::{CaptureError, CaptureRequest, CaptureTarget, ScreenCapture};
use os_linux::{
    Area, GrabError, Layout, LinuxScreenCapture, Monitor, RootGrab, RootImage, Snapshot, TreeWindow,
};

const MASKS: (u32, u32, u32) = (0x00ff_0000, 0x0000_ff00, 0x0000_00ff);
const PROCESS: u32 = 4242;
const ROOT: Area = Area {
    x: 0,
    y: 0,
    width: 2,
    height: 1,
};

type Calls = Arc<Mutex<Vec<Option<Area>>>>;

/// A fake root window with a scripted layout and grab; it records each call, `None` for a layout.
struct FakeRoot {
    layout: Result<Layout, GrabError>,
    answer: Result<RootImage, GrabError>,
    windows: Vec<TreeWindow>,
    composited: bool,
    calls: Calls,
}

impl RootGrab for FakeRoot {
    fn layout(&self) -> Result<Layout, GrabError> {
        self.calls
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(None);
        self.layout.clone()
    }

    fn grab(&self, area: Area) -> Result<Snapshot, GrabError> {
        self.calls
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .push(Some(area));
        self.answer.clone().map(|image| Snapshot {
            image,
            windows: self.windows.clone(),
            composited: self.composited,
        })
    }
}

fn monitor(primary: bool, x: i16) -> Monitor {
    Monitor {
        primary,
        area: Area {
            x,
            y: 0,
            width: 1,
            height: 1,
        },
    }
}

fn root_only() -> Layout {
    Layout {
        root: ROOT,
        monitors: Vec::new(),
    }
}

fn image(lsb_first: bool, data: Vec<u8>) -> RootImage {
    RootImage {
        width: 2,
        height: 1,
        depth: 24,
        bits_per_pixel: 32,
        lsb_first,
        masks: MASKS,
        data,
    }
}

/// A window of `pid` at `x`, `y` with a one pixel inside and the given border.
fn window(parent: Option<usize>, x: i16, y: i16, border: u16, pid: Option<u32>) -> TreeWindow {
    TreeWindow {
        parent,
        area: Area {
            x,
            y,
            width: 1,
            height: 1,
        },
        border,
        viewable: true,
        pid,
    }
}

/// A hidden window of this process, so a capture finds the process and paints nothing.
fn hidden() -> TreeWindow {
    TreeWindow {
        viewable: false,
        ..window(None, 0, 0, 0, Some(PROCESS))
    }
}

fn counted(
    layout: Result<Layout, GrabError>,
    answer: Result<RootImage, GrabError>,
) -> (LinuxScreenCapture<FakeRoot>, Calls) {
    let calls = Arc::new(Mutex::new(Vec::new()));
    let root = FakeRoot {
        layout,
        answer,
        windows: vec![hidden()],
        composited: false,
        calls: Arc::clone(&calls),
    };
    (LinuxScreenCapture::new(root, PROCESS), calls)
}

/// Captures a 4 by 3 monitor at 1, 1 of the root with `windows` over it, and returns which of its
/// pixels came back black, row by row.
fn blacked(windows: Vec<TreeWindow>) -> Result<Vec<String>, CaptureError> {
    let area = Area {
        x: 1,
        y: 1,
        width: 4,
        height: 3,
    };
    let layout = Layout {
        root: ROOT,
        monitors: vec![Monitor {
            primary: true,
            area,
        }],
    };
    let mut lit = image(true, vec![7; 48]);
    (lit.width, lit.height) = (4, 3);
    let root = FakeRoot {
        layout: Ok(layout),
        answer: Ok(lit),
        windows,
        composited: false,
        calls: Arc::new(Mutex::new(Vec::new())),
    };
    let frame = LinuxScreenCapture::new(root, PROCESS).capture(&display())?;
    let marks = frame.frame().pixels().chunks_exact(16).map(|row| {
        row.chunks_exact(4)
            .map(|pixel| if pixel == [0; 4] { '#' } else { '.' })
            .collect()
    });
    Ok(marks.collect())
}

fn backend(answer: Result<RootImage, GrabError>) -> LinuxScreenCapture<FakeRoot> {
    counted(Ok(root_only()), answer).0
}

fn calls_for(monitors: Vec<Monitor>) -> Vec<Option<Area>> {
    let layout = Layout {
        root: ROOT,
        monitors,
    };
    let (capture, calls) = counted(Ok(layout), Ok(image(true, vec![0; 8])));

    capture
        .capture(&display())
        .unwrap_or_else(|error| panic!("{error:?}"));

    calls.lock().unwrap_or_else(PoisonError::into_inner).clone()
}

fn display() -> CaptureRequest {
    CaptureRequest::new(0)
}

#[test]
fn a_least_significant_byte_first_image_is_already_bgra() {
    let capture = backend(Ok(image(true, vec![1, 2, 3, 9, 4, 5, 6, 9])));

    let frame = capture
        .capture(&display())
        .unwrap_or_else(|error| panic!("{error:?}"));

    assert_eq!(frame.frame().pixels(), &[1, 2, 3, 9, 4, 5, 6, 9]);
    assert_eq!((frame.frame().width(), frame.frame().height()), (2, 1));
}

#[test]
fn a_most_significant_byte_first_image_is_reordered_to_bgra() {
    let capture = backend(Ok(image(false, vec![9, 3, 2, 1, 9, 6, 5, 4])));

    let frame = capture
        .capture(&display())
        .unwrap_or_else(|error| panic!("{error:?}"));

    assert_eq!(frame.frame().pixels(), &[1, 2, 3, 9, 4, 5, 6, 9]);
}

#[test]
fn a_depth_32_root_is_read() {
    let mut deep = image(true, vec![0; 8]);
    deep.depth = 32;

    assert!(backend(Ok(deep)).capture(&display()).is_ok());
}

#[test]
fn a_whole_display_capture_has_no_window() {
    let frame = backend(Ok(image(true, vec![0; 8])))
        .capture(&display())
        .unwrap_or_else(|error| panic!("{error:?}"));

    assert_eq!(
        frame,
        body_core::CapturedFrame::display(frame.frame().clone())
    );
}

#[test]
fn a_layout_other_than_eight_bit_rgb_in_32_bits_is_refused() {
    let layouts = [
        (16, 32, MASKS),
        (24, 24, MASKS),
        (24, 32, (0x0000_00ff, 0x0000_ff00, 0x00ff_0000)),
        (24, 32, (0, 0, 0)),
    ];
    for (depth, bits_per_pixel, masks) in layouts {
        let mut odd = image(true, vec![0; 8]);
        odd.depth = depth;
        odd.bits_per_pixel = bits_per_pixel;
        odd.masks = masks;

        let captured = backend(Ok(odd)).capture(&display());

        let Err(CaptureError::Backend(reason)) = captured else {
            panic!("expected a refusal of {depth}/{bits_per_pixel}/{masks:x?}, got {captured:?}");
        };
        assert!(
            reason.contains(&format!("depth {depth} at {bits_per_pixel} bits")),
            "{reason}"
        );
    }
}

#[test]
fn a_short_buffer_is_a_backend_failure() {
    let captured = backend(Ok(image(true, vec![0; 4]))).capture(&display());

    assert!(
        matches!(captured, Err(CaptureError::Backend(_))),
        "{captured:?}"
    );
}

#[test]
fn the_primary_monitor_is_read_rather_than_the_whole_root() {
    let primary = monitor(true, 1);

    let calls = calls_for(vec![monitor(false, 0), primary]);

    assert_eq!(calls, vec![None, Some(primary.area)]);
}

#[test]
fn with_no_primary_the_first_listed_monitor_is_read() {
    let first = monitor(false, 1);

    let calls = calls_for(vec![first, monitor(false, 0)]);

    assert_eq!(calls, vec![None, Some(first.area)]);
}

#[test]
fn with_no_monitors_listed_the_whole_root_is_read() {
    assert_eq!(calls_for(Vec::new()), vec![None, Some(ROOT)]);
}

#[test]
fn a_failed_layout_is_a_backend_failure_without_a_read() {
    let (capture, calls) = counted(
        Err(GrabError::Failed(String::from("BadRequest"))),
        Ok(image(true, vec![0; 8])),
    );

    let captured = capture.capture(&display());

    assert_eq!(
        captured,
        Err(CaptureError::Backend(String::from("BadRequest")))
    );
    assert_eq!(
        *calls.lock().unwrap_or_else(PoisonError::into_inner),
        vec![None]
    );
}

#[test]
fn no_server_is_no_display() {
    let (capture, _) = counted(
        Err(GrabError::NoDisplay(String::from("DISPLAY is not set"))),
        Ok(image(true, vec![0; 8])),
    );

    let captured = capture.capture(&display());

    assert_eq!(
        captured,
        Err(CaptureError::NoDisplay(String::from("DISPLAY is not set")))
    );
}

#[test]
fn a_failed_read_is_a_backend_failure() {
    let captured = backend(Err(GrabError::Failed(String::from("BadMatch")))).capture(&display());

    assert_eq!(
        captured,
        Err(CaptureError::Backend(String::from("BadMatch")))
    );
}

#[test]
fn a_window_target_is_refused_without_reading_the_screen() {
    let (capture, calls) = counted(Ok(root_only()), Ok(image(true, vec![0; 8])));

    let captured = capture.capture(&CaptureRequest::targeted(0, 0, CaptureTarget::Focus));

    assert_eq!(
        captured,
        Err(CaptureError::Backend(String::from(
            "capturing one window is not implemented on X11"
        )))
    );
    assert!(
        calls
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .is_empty()
    );
}

fn rows(marks: [&str; 3]) -> Vec<String> {
    marks.map(String::from).to_vec()
}

#[test]
fn a_viewable_window_of_this_process_is_painted_black() {
    let painted = blacked(vec![window(None, 2, 1, 0, Some(PROCESS))]);

    assert_eq!(painted, Ok(rows([".#..", "....", "...."])));
}

#[test]
fn a_border_is_painted_with_its_window() {
    let painted = blacked(vec![window(None, 1, 1, 1, Some(PROCESS))]);

    assert_eq!(painted, Ok(rows(["###.", "###.", "###."])));
}

#[test]
fn a_window_inside_a_frame_is_placed_from_the_frames_inside_corner() {
    let frame = window(None, 1, 2, 1, None);

    let painted = blacked(vec![frame, window(Some(0), 1, 0, 0, Some(PROCESS))]);

    assert_eq!(painted, Ok(rows(["....", "....", "..#."])));
}

#[test]
fn a_window_partly_off_the_monitor_is_painted_where_it_overlaps() {
    let painted = blacked(vec![window(None, -1, 0, 1, Some(PROCESS))]);

    assert_eq!(painted, Ok(rows(["#...", "#...", "...."])));
}

#[test]
fn hidden_windows_and_other_processes_windows_are_left_alone() {
    let mut unmapped = window(None, 1, 1, 0, Some(PROCESS));
    unmapped.viewable = false;

    let painted = blacked(vec![unmapped, window(None, 2, 1, 0, Some(77))]);

    assert_eq!(painted, Ok(rows(["....", "....", "...."])));
}

#[test]
fn a_tree_with_no_window_of_this_process_is_refused() {
    let painted = blacked(vec![
        window(None, 1, 1, 0, None),
        window(None, 2, 1, 0, Some(77)),
    ]);

    let Err(CaptureError::Backend(reason)) = painted else {
        panic!("expected a refusal, got {painted:?}");
    };
    assert!(reason.contains("_NET_WM_PID"), "{reason}");
}

#[test]
fn a_parent_listed_after_its_child_is_refused() {
    let painted = blacked(vec![
        window(None, 0, 0, 0, None),
        window(Some(2), 0, 0, 0, Some(PROCESS)),
        window(None, 0, 0, 0, None),
    ]);

    let Err(CaptureError::Backend(reason)) = painted else {
        panic!("expected a refusal, got {painted:?}");
    };
    assert!(reason.contains("parent"), "{reason}");
}

#[test]
fn a_screen_a_compositing_manager_paints_is_refused() {
    let root = FakeRoot {
        layout: Ok(root_only()),
        answer: Ok(image(true, vec![7; 8])),
        windows: vec![window(None, 0, 0, 0, Some(PROCESS))],
        composited: true,
        calls: Arc::new(Mutex::new(Vec::new())),
    };

    let captured = LinuxScreenCapture::new(root, PROCESS)
        .capture(&display())
        .map(|_| ());

    let Err(CaptureError::Backend(reason)) = captured else {
        panic!("expected a refusal, got {captured:?}");
    };
    assert!(reason.contains("compositing manager"), "{reason}");
}
