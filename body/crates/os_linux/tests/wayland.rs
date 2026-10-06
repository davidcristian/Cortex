#![cfg(target_os = "linux")]

use std::io::Write;
use std::os::fd::OwnedFd;
use std::os::unix::net::UnixStream;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::thread;
use std::time::Duration;

use os_linux::wayland_client::{ConnectError, Connection};
use os_linux::{SelectionError, SelectionRead, WaylandSelection};
use wayland_protocols::ext::data_control::v1::server::ext_data_control_device_v1::ExtDataControlDeviceV1;
use wayland_protocols::ext::data_control::v1::server::ext_data_control_manager_v1::{
    self as ext_manager, ExtDataControlManagerV1,
};
use wayland_protocols::ext::data_control::v1::server::ext_data_control_offer_v1::{
    self as ext_offer, ExtDataControlOfferV1,
};
use wayland_protocols_wlr::data_control::v1::server::zwlr_data_control_device_v1::ZwlrDataControlDeviceV1;
use wayland_protocols_wlr::data_control::v1::server::zwlr_data_control_manager_v1::{
    self as wlr_manager, ZwlrDataControlManagerV1,
};
use wayland_protocols_wlr::data_control::v1::server::zwlr_data_control_offer_v1::{
    self as wlr_offer, ZwlrDataControlOfferV1,
};
use wayland_server::backend::{ClientData, ClientId, DisconnectReason, GlobalId};
use wayland_server::protocol::wl_seat::{self, WlSeat};
use wayland_server::{
    Client, DataInit, Dispatch, Display, DisplayHandle, GlobalDispatch, New, Resource,
};

const PNG: &str = "image/png";
const TEXT: &str = "text/plain";
const LIMIT: usize = 1 << 20;

/// What the fake compositor lists and how its selection's owner answers.
#[derive(Clone)]
struct Script {
    seat: Seat,
    ext: bool,
    wlr: bool,
    selection: Option<Vec<&'static str>>,
    answer: Answer,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Seat {
    Listed,
    Missing,
    /// Listed, with a protocol error for a device asked for on it.
    Refused,
}

#[derive(Clone)]
enum Answer {
    Bytes(Vec<u8>),
    Hold,
    Reject,
}

impl Script {
    fn ext(types: &[&'static str], answer: Answer) -> Self {
        Self {
            seat: Seat::Listed,
            ext: true,
            wlr: true,
            selection: Some(types.to_vec()),
            answer,
        }
    }
}

struct Compositor {
    script: Script,
    spare: Option<GlobalId>,
    held: Vec<OwnedFd>,
    asked: Vec<String>,
}

struct Peer(Arc<AtomicBool>);

impl ClientData for Peer {
    fn disconnected(&self, _: ClientId, _: DisconnectReason) {
        self.0.store(true, Ordering::SeqCst);
    }
}

/// Serves `script` on one end of a socket pair and connects the read to the other.
fn serve(script: Script) -> WaylandSelection {
    serve_with(script, Duration::from_secs(1))
}

fn serve_with(script: Script, limit: Duration) -> WaylandSelection {
    let (client, server) = UnixStream::pair().unwrap_or_else(|error| panic!("{error:?}"));
    thread::spawn(move || run(script, server));
    let connection = Connection::from_socket(client).unwrap_or_else(|error| panic!("{error:?}"));
    WaylandSelection::with_limit(connection, limit)
}

fn run(script: Script, server: UnixStream) {
    let mut display: Display<Compositor> =
        Display::new().unwrap_or_else(|error| panic!("{error:?}"));
    let mut handle = display.handle();
    let mut spare = None;
    if script.seat != Seat::Missing {
        handle.create_global::<Compositor, WlSeat, ()>(1, ());
        spare = Some(handle.create_global::<Compositor, WlSeat, ()>(1, ()));
    }
    if script.ext {
        handle.create_global::<Compositor, ExtDataControlManagerV1, ()>(1, ());
    }
    if script.wlr {
        handle.create_global::<Compositor, ZwlrDataControlManagerV1, ()>(2, ());
    }
    let gone = Arc::new(AtomicBool::new(false));
    handle
        .insert_client(server, Arc::new(Peer(Arc::clone(&gone))))
        .unwrap_or_else(|error| panic!("{error:?}"));
    let mut state = Compositor {
        script,
        spare,
        held: Vec::new(),
        asked: Vec::new(),
    };
    while !gone.load(Ordering::SeqCst) {
        let _ = display.dispatch_clients(&mut state);
        let _ = display.flush_clients();
        thread::sleep(Duration::from_millis(1));
    }
}

impl Compositor {
    /// Drops the spare seat, then sends the selection the way a compositor does on a new device.
    fn announce<O: Resource + 'static>(
        &mut self,
        handle: &DisplayHandle,
        client: &Client,
        version: u32,
        shadowed: bool,
        introduce: impl Fn(&O, Vec<&'static str>),
        send: impl FnOnce(Option<&O>),
    ) where
        Self: Dispatch<O, ()>,
    {
        if let Some(spare) = self.spare.take() {
            handle.remove_global::<Self>(spare);
        }
        let Some(types) = self.script.selection.clone() else {
            send(None);
            return;
        };
        let made = client.create_resource::<O, (), Self>(handle, version, ());
        let made = made.unwrap_or_else(|error| panic!("{error:?}"));
        // A read that picks `wlr` over a listed `ext` sees an empty list.
        introduce(&made, types.into_iter().filter(|_| !shadowed).collect());
        send(Some(&made));
    }

    fn receive(&mut self, mime_type: String, fd: OwnedFd, reject: impl FnOnce()) {
        self.asked.push(mime_type);
        match self.script.answer.clone() {
            Answer::Bytes(bytes) => {
                thread::spawn(move || {
                    let _ = std::fs::File::from(fd).write_all(&bytes);
                });
            }
            Answer::Hold => self.held.push(fd),
            Answer::Reject => reject(),
        }
    }
}

impl GlobalDispatch<WlSeat, ()> for Compositor {
    fn bind(
        _: &mut Self,
        _: &DisplayHandle,
        _: &Client,
        seat: New<WlSeat>,
        (): &(),
        init: &mut DataInit<'_, Self>,
    ) {
        init.init(seat, ())
            .capabilities(wl_seat::Capability::Keyboard);
    }
}

impl Dispatch<WlSeat, ()> for Compositor {
    fn request(
        _: &mut Self,
        _: &Client,
        _: &WlSeat,
        _: wl_seat::Request,
        (): &(),
        _: &DisplayHandle,
        _: &mut DataInit<'_, Self>,
    ) {
    }
}

macro_rules! protocol {
    ($manager:ty, $manager_mod:ident, $device:ty, $offer:ty, $offer_mod:ident, $wlr:expr) => {
        impl GlobalDispatch<$manager, ()> for Compositor {
            fn bind(
                _: &mut Self,
                _: &DisplayHandle,
                _: &Client,
                manager: New<$manager>,
                (): &(),
                init: &mut DataInit<'_, Self>,
            ) {
                init.init(manager, ());
            }
        }

        impl Dispatch<$manager, ()> for Compositor {
            fn request(
                state: &mut Self,
                client: &Client,
                _: &$manager,
                request: $manager_mod::Request,
                (): &(),
                handle: &DisplayHandle,
                init: &mut DataInit<'_, Self>,
            ) {
                if let $manager_mod::Request::GetDataDevice { id, .. } = request {
                    let device = init.init(id, ());
                    if state.script.seat == Seat::Refused {
                        device.post_error(0_u32, "no device for this seat");
                        return;
                    }
                    let version = device.version();
                    let shadowed = $wlr && state.script.ext;
                    state.announce::<$offer>(
                        handle,
                        client,
                        version,
                        shadowed,
                        |offer, types| {
                            device.data_offer(offer);
                            for name in types {
                                offer.offer(String::from(name));
                            }
                        },
                        |offer| device.selection(offer),
                    );
                }
            }
        }

        impl Dispatch<$device, ()> for Compositor {
            fn request(
                _: &mut Self,
                _: &Client,
                _: &$device,
                _: <$device as Resource>::Request,
                (): &(),
                _: &DisplayHandle,
                _: &mut DataInit<'_, Self>,
            ) {
            }
        }

        impl Dispatch<$offer, ()> for Compositor {
            fn request(
                state: &mut Self,
                _: &Client,
                offer: &$offer,
                request: $offer_mod::Request,
                (): &(),
                _: &DisplayHandle,
                _: &mut DataInit<'_, Self>,
            ) {
                if let $offer_mod::Request::Receive { mime_type, fd } = request {
                    state.receive(mime_type, fd, || offer.post_error(0_u32, "rejected"));
                }
            }
        }
    };
}

protocol!(
    ExtDataControlManagerV1,
    ext_manager,
    ExtDataControlDeviceV1,
    ExtDataControlOfferV1,
    ext_offer,
    false
);
protocol!(
    ZwlrDataControlManagerV1,
    wlr_manager,
    ZwlrDataControlDeviceV1,
    ZwlrDataControlOfferV1,
    wlr_offer,
    true
);

fn picture(size: usize) -> Vec<u8> {
    (0..size)
        .map(|index| u8::try_from(index % 251).unwrap_or_default())
        .collect()
}

#[test]
fn offered_lists_the_selection_types_in_order() {
    let read = serve(Script::ext(&[TEXT, PNG], Answer::Hold));
    assert_eq!(
        read.offered(),
        Ok(vec![String::from(TEXT), String::from(PNG)])
    );
}

#[test]
fn convert_reads_a_picture_over_many_chunks_through_ext() {
    let bytes = picture(200_000);
    let read = serve(Script::ext(&[PNG], Answer::Bytes(bytes.clone())));
    assert_eq!(read.convert(PNG, LIMIT), Ok(Some(bytes)));
}

#[test]
fn convert_reads_through_wlr_when_ext_is_not_listed() {
    let bytes = picture(1000);
    let script = Script {
        ext: false,
        ..Script::ext(&[TEXT, PNG], Answer::Bytes(bytes.clone()))
    };
    let read = serve(script);
    assert_eq!(
        read.offered(),
        Ok(vec![String::from(TEXT), String::from(PNG)])
    );
    assert_eq!(read.convert(PNG, LIMIT), Ok(Some(bytes)));
}

#[test]
fn an_empty_answer_is_kept_as_empty_bytes() {
    let read = serve(Script::ext(&[PNG], Answer::Bytes(Vec::new())));
    assert_eq!(read.convert(PNG, LIMIT), Ok(Some(Vec::new())));
}

#[test]
fn no_selection_lists_nothing_and_converts_to_none() {
    let script = Script {
        selection: None,
        ..Script::ext(&[], Answer::Hold)
    };
    let read = serve(script);
    assert_eq!(read.offered(), Ok(Vec::new()));
    assert_eq!(read.convert(PNG, LIMIT), Ok(None));
}

#[test]
fn a_selection_with_no_types_lists_nothing() {
    let read = serve(Script::ext(&[], Answer::Hold));
    assert_eq!(read.offered(), Ok(Vec::new()));
}

#[test]
fn an_answer_past_the_limit_is_over() {
    let read = serve(Script::ext(&[PNG], Answer::Bytes(picture(101))));
    assert_eq!(read.convert(PNG, 100), Err(SelectionError::Over));
}

#[test]
fn an_answer_at_the_limit_is_read() {
    let bytes = picture(100);
    let read = serve(Script::ext(&[PNG], Answer::Bytes(bytes.clone())));
    assert_eq!(read.convert(PNG, 100), Ok(Some(bytes)));
}

#[test]
fn an_owner_that_never_writes_is_silent() {
    let script = Script::ext(&[PNG], Answer::Hold);
    let read = serve_with(script, Duration::from_millis(50));
    assert_eq!(read.convert(PNG, LIMIT), Err(SelectionError::Silent));
}

#[test]
fn a_compositor_with_no_seat_fails() {
    let script = Script {
        seat: Seat::Missing,
        ..Script::ext(&[PNG], Answer::Hold)
    };
    let failed = SelectionError::Failed(String::from("the compositor lists no seat"));
    assert_eq!(serve(script).offered(), Err(failed));
}

#[test]
fn a_compositor_with_neither_protocol_fails() {
    let script = Script {
        ext: false,
        wlr: false,
        ..Script::ext(&[PNG], Answer::Hold)
    };
    let reason = "the compositor offers no data control protocol";
    let failed = SelectionError::Failed(String::from(reason));
    assert_eq!(serve(script).convert(PNG, LIMIT), Err(failed));
}

#[test]
fn a_closed_connection_fails() {
    let (client, server) = UnixStream::pair().unwrap_or_else(|error| panic!("{error:?}"));
    drop(server);
    let connection = Connection::from_socket(client).unwrap_or_else(|error| panic!("{error:?}"));
    let read = WaylandSelection::new(connection);
    assert!(matches!(read.offered(), Err(SelectionError::Failed(_))));
    assert!(matches!(
        read.convert(PNG, LIMIT),
        Err(SelectionError::Failed(_))
    ));
}

#[test]
fn an_absent_compositor_fails_with_its_reason() {
    let read = WaylandSelection::absent(&ConnectError::NoCompositor);
    let failed = SelectionError::Failed(ConnectError::NoCompositor.to_string());
    assert_eq!(read.offered(), Err(failed.clone()));
    assert_eq!(read.convert(PNG, LIMIT), Err(failed));
}

#[test]
fn a_rejected_device_fails() {
    let script = Script {
        seat: Seat::Refused,
        ..Script::ext(&[PNG], Answer::Hold)
    };
    let read = serve(script);
    assert!(
        matches!(read.offered(), Err(SelectionError::Failed(text)) if text.contains("no device"))
    );
}

#[test]
fn a_rejected_receive_fails() {
    let read = serve(Script::ext(&[PNG], Answer::Reject));
    assert!(
        matches!(read.convert(PNG, LIMIT), Err(SelectionError::Failed(text)) if text.contains("rejected"))
    );
}
