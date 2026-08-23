//! What a 4K desktop costs in PNG bytes at the edge the brain asks for, and how much room is
//! left before the halving ladder fires (ADR-0029's legibility addendum).
//!
//! The brain asks for a 2048 px capture by default now, because that is the half of the measured
//! legibility pair the body can supply. A bigger edge is a bigger PNG, and a PNG over
//! [`MAX_CAPTURE_BYTES`] does not fail: it silently halves the capture to 1024 px, which is worse
//! than the 1600 px view the default replaced. So the default is only safe if a screen a person
//! would actually read text off stays inside the ceiling, and that is what this file measures.
//!
//! **These are byte fixtures, not a legibility corpus.** What a PNG costs is decided by how
//! compressible the picture is, so each screen here is built out of the two things that decide
//! that on a real desktop: smooth photographic structure (three octaves of value noise per
//! channel, which is what a wallpaper or a video still is to a compressor) and high-frequency
//! detail (film grain, and ink runs at the spatial frequency of interface text). None of it is
//! readable, and none of it needs to be. The legibility half is measured against the real cortex
//! in `brain/packages/inference/tests/test_image_budget_live.py`.
//!
//! The grain is added at the **source** resolution and then averaged down by the body's own box
//! filter, exactly as a real capture is, which is the whole reason a 2048 px capture costs so
//! much more than a 1600 px one: the wider edge averages fewer source pixels per output pixel, so
//! more of the noise survives, over more pixels.
//!
//! That is also why the display's own size is a variable here rather than a constant. What decides
//! how much grain survives is the **ratio** between the display and the requested edge, so the
//! costliest screen is not the biggest one: a 4K display averages three and a half source pixels
//! into each output pixel and most of the grain dies there, a 2560x1440 display averages almost
//! nothing, and a 1920x1080 display is inside the bound already and crosses the seam untouched.
//!
//! `#[ignore]`d: it is 4 s of CPU on 33 MB frames in release and 48 s of it unoptimized, which
//! is the shape `just check` runs, so it is a measurement rather than a gate. It is not on every
//! commit's critical path for a number that only moves when the capture edge, the byte ceiling,
//! or the downscaler does. Re-run it when one of those changes:
//!
//! ```text
//! cargo test -p body-core --test capture_bytes --release -- --ignored --nocapture --test-threads=1
//! ```

use std::fmt::Debug;

use body_core::os::screen_policy::{DEFAULT_MAX_EDGE, MAX_CAPTURE_BYTES};
use body_core::{Capture, CaptureRequest, CapturedFrame, RawFrame, TargetRect};

/// The display the desktop fixtures are built at: one 4K screen, which is what the capture path
/// is bounded for and the size the legibility measurement was taken on. It is the default rather
/// than the only one, since [`WORST_DISPLAY`] costs more.
const SOURCE: (u32, u32) = (3840, 2160);

/// The body's own default edge, what a caller that asks for nothing still gets.
///
/// Read from the policy rather than spelled, which is the difference between this and
/// [`BRAIN_EDGE`] below. Both are numbers this suite must follow rather than choose, and neither
/// is a fixture; but this one is declared in a crate the suite already imports, so the compiler
/// holds it and nothing else has to. The brain's lives in another language, where no compiler
/// reaches, which is why that one is spelled here and tied by `scripts/crosscheck.py` instead.
const BODY_EDGE: u32 = DEFAULT_MAX_EDGE;

/// The edge the brain asks for by default from this slice on.
const BRAIN_EDGE: u32 = 2048;

/// Unwraps a fixture's result. `unwrap` is denied outside `#[test]` bodies, and these run
/// outside one.
fn ok<T, E: Debug>(result: Result<T, E>) -> T {
    result.unwrap_or_else(|error| panic!("the fixture failed: {error:?}"))
}

/// A tiny linear congruential generator, so every number this file prints is reproducible.
struct Rng(u64);

impl Rng {
    fn new(seed: u64) -> Self {
        Self(seed)
    }

    fn next_byte(&mut self) -> u8 {
        self.0 = self
            .0
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        u8::try_from((self.0 >> 33) & 0xff).unwrap_or_default()
    }
}

/// One octave of value noise: a coarse random lattice, read back bilinearly at screen size.
struct Octave {
    cells_x: usize,
    cells_y: usize,
    values: Vec<u8>,
}

impl Octave {
    fn new(cells_x: usize, cells_y: usize, rng: &mut Rng) -> Self {
        let values = (0..cells_x * cells_y).map(|_| rng.next_byte()).collect();
        Self {
            cells_x,
            cells_y,
            values,
        }
    }

    /// The lattice sampled at `(x, y)` of a `width x height` screen, bilinear in 8-bit fixed
    /// point so the whole synthesis stays in integer arithmetic.
    fn sample(&self, x: usize, y: usize, width: usize, height: usize) -> i32 {
        let (fx, tx) = Self::split(x, self.cells_x, width);
        let (fy, ty) = Self::split(y, self.cells_y, height);
        let row = |at: usize| {
            let left = i32::from(self.values[at * self.cells_x + fx]);
            let right = i32::from(self.values[at * self.cells_x + (fx + 1).min(self.cells_x - 1)]);
            left * (256 - tx) + right * tx
        };
        let top = row(fy);
        let bottom = row((fy + 1).min(self.cells_y - 1));
        (top * (256 - ty) + bottom * ty) >> 16
    }

    /// The lattice cell a screen coordinate falls in, and how far into it, in 1/256ths.
    fn split(at: usize, cells: usize, span: usize) -> (usize, i32) {
        let scaled = at * (cells - 1) * 256 / span;
        (scaled >> 8, i32::try_from(scaled & 255).unwrap_or_default())
    }
}

/// A BGRA screen under construction. Top-down, four bytes a pixel, alpha left where a blit
/// leaves it, which is what [`RawFrame`] is documented to receive.
struct Screen {
    width: usize,
    height: usize,
    pixels: Vec<u8>,
}

impl Screen {
    fn new(source: (u32, u32)) -> Self {
        let (width, height) = (source.0 as usize, source.1 as usize);
        Self {
            width,
            height,
            pixels: vec![0; width * height * 4],
        }
    }

    fn set(&mut self, x: usize, y: usize, blue: i32, green: i32, red: i32) {
        let at = (y * self.width + x) * 4;
        self.pixels[at] = clamp(blue);
        self.pixels[at + 1] = clamp(green);
        self.pixels[at + 2] = clamp(red);
    }

    /// Paints a photograph over the whole screen: three octaves of value noise per channel,
    /// plus per-pixel film grain of `grain` counts either way.
    fn photograph(&mut self, grain: i32, rng: &mut Rng) {
        let channels: Vec<[Octave; 3]> = (0..3)
            .map(|_| {
                [
                    Octave::new(9, 6, rng),
                    Octave::new(41, 24, rng),
                    Octave::new(161, 91, rng),
                ]
            })
            .collect();
        for y in 0..self.height {
            for x in 0..self.width {
                let mut colour = [0_i32; 3];
                for (channel, octaves) in colour.iter_mut().zip(&channels) {
                    *channel = octaves[0].sample(x, y, self.width, self.height) / 2
                        + octaves[1].sample(x, y, self.width, self.height) / 3
                        + octaves[2].sample(x, y, self.width, self.height) / 6
                        + grain_of(grain, rng);
                }
                self.set(x, y, colour[0], colour[1], colour[2]);
            }
        }
    }

    /// Fills a rectangle flat, the way every piece of interface chrome compresses.
    fn panel(&mut self, x: usize, y: usize, width: usize, height: usize, shade: i32) {
        for row in y..(y + height).min(self.height) {
            for column in x..(x + width).min(self.width) {
                self.set(column, row, shade, shade, shade + 4);
            }
        }
    }

    /// Paints rows of ink runs at the spatial frequency interface text has: strokes one to
    /// three pixels wide with gaps of the same order, which is what a downscaler has to average
    /// and what a compressor cannot predict.
    fn text_rows(&mut self, x: usize, y: usize, width: usize, rows: usize, rng: &mut Rng) {
        for row in 0..rows {
            let top = y + row * 30;
            if top + 16 >= self.height {
                return;
            }
            let mut column = x;
            while column + 4 < (x + width).min(self.width) {
                let stroke = 1 + usize::from(rng.next_byte() % 3);
                let gap = 1 + usize::from(rng.next_byte() % 4);
                let ink = 40 + i32::from(rng.next_byte() % 24);
                self.panel(column, top, stroke, 14, ink);
                column += stroke + gap;
            }
        }
    }

    fn frame(self) -> RawFrame {
        let (width, height) = (
            ok(u32::try_from(self.width)),
            ok(u32::try_from(self.height)),
        );
        ok(RawFrame::new(width, height, self.pixels))
    }
}

fn clamp(value: i32) -> u8 {
    u8::try_from(value.clamp(0, 255)).unwrap_or(u8::MAX)
}

/// One pixel's worth of grain, or nothing at all when the fixture asked for none.
fn grain_of(grain: i32, rng: &mut Rng) -> i32 {
    if grain == 0 {
        return 0;
    }
    i32::from(rng.next_byte()) % (2 * grain + 1) - grain
}

/// A desktop with a photographic wallpaper and two windows of text over it, which is what a
/// screen a person asks about usually is.
fn wallpaper_desktop(grain: i32) -> RawFrame {
    let mut rng = Rng::new(0x5EED_0001);
    let mut screen = Screen::new(SOURCE);
    screen.photograph(grain, &mut rng);
    screen.panel(0, 2100, 3840, 60, 32);
    for (left, top) in [(120, 140), (1960, 720)] {
        screen.panel(left, top, 1720, 1200, 244);
        screen.panel(left, top, 1720, 46, 226);
        screen.text_rows(left + 40, top + 90, 1640, 36, &mut rng);
    }
    screen.frame()
}

/// A photograph filling the display: a maximised viewer, a video still, a full-bleed page. The
/// realistic worst case, since nothing flat is left to compress.
fn full_screen_photograph(grain: i32) -> RawFrame {
    full_screen_photograph_on(SOURCE, grain)
}

/// The same photograph on a display of any size, because how much grain survives the downscale
/// is decided by the *ratio* between the display and the requested edge rather than by either
/// number alone. A 4K screen averages three and a half source pixels into every output pixel and
/// most of the grain dies there; a display closer to the requested edge averages barely anything.
fn full_screen_photograph_on(source: (u32, u32), grain: i32) -> RawFrame {
    let mut rng = Rng::new(0x5EED_0002);
    let mut screen = Screen::new(source);
    screen.photograph(grain, &mut rng);
    screen.frame()
}

/// The screen this whole setting exists for: flat panels and nothing but small text.
fn text_desktop() -> RawFrame {
    let mut rng = Rng::new(0x5EED_0003);
    let mut screen = Screen::new(SOURCE);
    screen.panel(0, 0, 3840, 2160, 24);
    screen.panel(0, 0, 2200, 2160, 30);
    screen.panel(2200, 0, 1640, 2160, 250);
    screen.text_rows(60, 40, 2080, 70, &mut rng);
    screen.text_rows(2260, 40, 1520, 70, &mut rng);
    screen.frame()
}

/// Uniform per-pixel noise: not a screen anyone has, and the incompressible bound the ladder
/// exists for.
fn uniform_noise() -> RawFrame {
    let mut rng = Rng::new(0x5EED_0004);
    let mut screen = Screen::new(SOURCE);
    for y in 0..screen.height {
        for x in 0..screen.width {
            let (blue, green, red) = (rng.next_byte(), rng.next_byte(), rng.next_byte());
            screen.set(x, y, i32::from(blue), i32::from(green), i32::from(red));
        }
    }
    screen.frame()
}

/// The size a region of `source` comes back at when the brain asks for [`BRAIN_EDGE`]: the
/// policy's own rule, the longest edge landing on the bound and the other scaled by the same
/// ratio and floored, written once here instead of a pair of digits per case.
///
/// A case that pins that pair as digits fails in this suite the day the edge is retuned, with two
/// numbers nothing in the file explains, while every repo gate stays green. No registry row can
/// close that, and the reason is worth keeping: the height is not a second spelling of the edge,
/// it is a **consequence** of the edge and of the display's shape, so a needle over the pair would
/// tie two independent couplings into one and redden on a change to the fixture's aspect ratio.
/// Arithmetic here removes the coupling instead of holding it. What an assertion against this
/// gives up is an independently written floor; what it still catches is a capture that was not
/// resampled at all, one resampled to the wrong bound, one that lost its aspect ratio, and the
/// halving ladder firing.
fn brain_size(source: (u32, u32)) -> (u32, u32) {
    let longest = source.0.max(source.1);
    if longest <= BRAIN_EDGE {
        return source;
    }
    let scaled = |edge: u32| {
        ok(u32::try_from(
            u64::from(edge) * u64::from(BRAIN_EDGE) / u64::from(longest),
        ))
    };
    (scaled(source.0), scaled(source.1))
}

/// One frame through the real policy at one edge: the bytes that would cross the seam, and the
/// size they came back at, which is how the halving ladder announces itself.
fn measure(captured: &CapturedFrame, edge: u32) -> (usize, u32, u32) {
    let capture = ok(Capture::from_bgra(captured, &CaptureRequest::new(edge)));
    (capture.data().len(), capture.width(), capture.height())
}

/// Prints one screen's row and answers whether the wider edge kept the size it should have.
///
/// The bytes printed are always the ones that would cross the seam, so a row whose ladder fired
/// prints a *small* number at a *small* size, which is exactly the failure this default has to
/// avoid: the capture does not error, it silently arrives at 1024 px.
///
/// The size it should have is `min(the display's long edge, the requested edge)` rather than the
/// requested edge itself, because `downscale` never upscales: a display already inside the bound
/// crosses the seam pixel for pixel. Comparing against the request alone would call a 1920x1080
/// desktop's untouched 1920x1080 capture a fired ladder, which is how this measurement first read.
fn report(name: &str, frame: RawFrame) -> bool {
    let captured = CapturedFrame::display(frame);
    let (body_bytes, ..) = measure(&captured, BODY_EDGE);
    let (brain_bytes, width, height) = measure(&captured, BRAIN_EDGE);
    let display = captured.frame();
    let intact = width.max(height) == display.width().max(display.height()).min(BRAIN_EDGE);
    let verdict = if intact {
        format!("{}% of the ceiling", brain_bytes * 100 / MAX_CAPTURE_BYTES)
    } else {
        String::from("THE LADDER FIRED")
    };
    println!(
        "  {name:<32} {BODY_EDGE} px: {body_bytes:>9} B   {BRAIN_EDGE} px: {brain_bytes:>9} B \
         ({width}x{height}, {verdict})"
    );
    intact
}

/// One window of a display through the same policy: the bytes, and the size they came back at.
fn report_window(name: &str, frame: &RawFrame, window: TargetRect) -> (usize, u32, u32) {
    let captured = CapturedFrame::window(frame.clone(), window);
    let (bytes, width, height) = measure(&captured, BRAIN_EDGE);
    println!(
        "  {name:<32} {BRAIN_EDGE} px: {bytes:>9} B ({width}x{height}, {}% of the ceiling)",
        bytes * 100 / MAX_CAPTURE_BYTES
    );
    (bytes, width, height)
}

#[test]
#[ignore = "byte measurement on 4K frames: run with --release -- --ignored --nocapture"]
fn a_window_inside_the_capture_edge_crosses_at_its_own_resolution() {
    // The reason a targeted capture is worth the seam change, in bytes. The same 4K desktop as
    // the wallpaper row above: asked for whole, it is resampled to 2048 px and costs megabytes;
    // asked for as the window the user is reading, it crosses the seam untouched, so every
    // source pixel of the part that was asked about survives, at a fraction of the bytes.
    println!("\nOne window of a 4K wallpaper desktop, through the real crop and encode:");
    let frame = wallpaper_desktop(6);
    let (whole_bytes, ..) = measure(&CapturedFrame::display(frame.clone()), BRAIN_EDGE);
    println!("  the whole desktop, for scale     {BRAIN_EDGE} px: {whole_bytes:>9} B");

    let (window_bytes, width, height) = report_window(
        "a 1720x1200 text window",
        &frame,
        TargetRect::new(120, 140, 1840, 1340),
    );
    assert_eq!(
        (width, height),
        (1720, 1200),
        "a window inside the capture edge must cross pixel for pixel, not resampled"
    );
    assert!(
        window_bytes < whole_bytes,
        "the window costs {window_bytes} B against the desktop's {whole_bytes} B"
    );

    // A maximised window is the whole display again, which is the case that must not become
    // cheaper by accident: it is the same picture and it costs the same bytes.
    let (maximised, width, height) = report_window(
        "a maximised window",
        &frame,
        TargetRect::new(
            0,
            0,
            ok(i32::try_from(SOURCE.0)),
            ok(i32::try_from(SOURCE.1)),
        ),
    );
    assert_eq!(
        (width, height),
        brain_size(SOURCE),
        "a maximised window is the whole display, so it comes back resampled to the edge the \
         brain asks for rather than at its own resolution"
    );
    assert_eq!(maximised, whole_bytes);
}

#[test]
#[ignore = "byte measurement on 4K frames: run with --release -- --ignored --nocapture"]
fn a_screen_worth_reading_text_off_stays_inside_the_ceiling_at_the_edge_the_brain_asks_for() {
    println!("\n4K desktops through the real downscale and encode:");
    for (name, frame) in [
        ("text desktop", text_desktop()),
        ("wallpaper desktop", wallpaper_desktop(6)),
        ("full-screen photograph", full_screen_photograph(6)),
        ("photograph, heavy grain", full_screen_photograph(16)),
    ] {
        assert!(
            report(name, frame),
            "{name} fired the halving ladder at the {BRAIN_EDGE} px default, which would drop \
             the capture to 1024 px and undo the legibility the edge was raised to buy"
        );
    }
}

#[test]
#[ignore = "byte measurement on 4K frames: run with --release -- --ignored --nocapture"]
fn the_ladder_still_fires_on_a_screen_no_one_has() {
    println!("\nHow much room the {BRAIN_EDGE} px default has left, by how grainy the screen is:");
    for grain in [0, 8, 16, 32, 64] {
        report(
            &format!("photograph, grain {grain}"),
            full_screen_photograph(grain),
        );
    }
    println!("\nThe incompressible bound, which is not a screen anyone has:");
    assert!(
        !report("uniform noise", uniform_noise()),
        "uniform noise now fits inside {MAX_CAPTURE_BYTES} bytes at {BRAIN_EDGE} px, so either \
         the encoder or the ceiling moved and the margin recorded in the addendum is stale"
    );
}

/// The display that costs the most at the [`BRAIN_EDGE`] default, which is not the biggest one.
const WORST_DISPLAY: (u32, u32) = (2560, 1440);

#[test]
#[ignore = "byte measurement on 4K frames: run with --release -- --ignored --nocapture"]
fn a_display_nearer_the_requested_edge_is_the_expensive_one() {
    println!("\nThe same grainy photograph on the displays a person actually owns:");
    for source in [SOURCE, WORST_DISPLAY, (1920, 1080)] {
        assert!(
            report(
                &format!("photograph, grain 16, {}x{}", source.0, source.1),
                full_screen_photograph_on(source, 16),
            ),
            "a {}x{} display fired the halving ladder on an ordinary grainy photograph, which \
             the 4K measurement behind the {BRAIN_EDGE} px default did not predict",
            source.0,
            source.1
        );
    }
    println!("\nHow much room the costliest of those has left, by how grainy the screen is:");
    for grain in [0, 8, 16, 32, 64] {
        report(
            &format!("photograph, grain {grain}, 2560x1440"),
            full_screen_photograph_on(WORST_DISPLAY, grain),
        );
    }
}
