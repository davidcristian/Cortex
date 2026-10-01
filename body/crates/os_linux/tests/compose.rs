#![cfg(target_os = "linux")]

use os_linux::{Area, Piece, TreeWindow, pieces};

const SCREEN: Area = Area {
    x: 10,
    y: 20,
    width: 100,
    height: 50,
};

fn at(x: i16, y: i16, width: u16, height: u16) -> Area {
    Area {
        x,
        y,
        width,
        height,
    }
}

fn shown(area: Area, border: u16) -> TreeWindow {
    TreeWindow {
        parent: None,
        area,
        border,
        viewable: true,
        pid: None,
        input_only: false,
    }
}

#[test]
fn each_shown_top_level_window_is_read_whole_when_inside_the_screen_in_list_order() {
    let windows = [shown(at(30, 30, 5, 6), 0), shown(at(11, 21, 2, 3), 0)];

    assert_eq!(
        pieces(&windows, SCREEN),
        vec![
            Piece {
                window: 0,
                inside: at(0, 0, 5, 6),
                place: at(30, 30, 5, 6),
            },
            Piece {
                window: 1,
                inside: at(0, 0, 2, 3),
                place: at(11, 21, 2, 3),
            },
        ]
    );
}

#[test]
fn a_window_past_the_screen_is_read_only_where_it_overlaps_inside_its_border() {
    let windows = [shown(at(0, 0, 20, 30), 2), shown(at(100, 60, 30, 30), 0)];

    assert_eq!(
        pieces(&windows, SCREEN),
        vec![
            Piece {
                window: 0,
                inside: at(8, 18, 12, 12),
                place: at(10, 20, 12, 12),
            },
            Piece {
                window: 1,
                inside: at(0, 0, 10, 10),
                place: at(100, 60, 10, 10),
            },
        ]
    );
}

#[test]
fn hidden_child_input_only_and_off_screen_windows_are_not_read() {
    let mut hidden = shown(at(30, 30, 5, 5), 0);
    hidden.viewable = false;
    let mut child = shown(at(30, 30, 5, 5), 0);
    child.parent = Some(0);
    let mut input_only = shown(at(30, 30, 5, 5), 0);
    input_only.input_only = true;
    let windows = [
        hidden,
        child,
        input_only,
        shown(at(110, 30, 5, 5), 0),
        shown(at(30, 70, 5, 5), 0),
        shown(at(30, 0, 5, 20), 0),
    ];

    assert_eq!(pieces(&windows, SCREEN), Vec::new());
}
