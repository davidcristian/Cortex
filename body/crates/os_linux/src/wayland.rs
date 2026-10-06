//! The Wayland adapter for [`SelectionRead`](crate::SelectionRead), over the `ext` data control
//! protocol where the compositor lists it, else the `wlr` one.

use std::io::{self, PipeReader, Read as _};
use std::os::fd::AsFd;
use std::time::Duration;

use crate::clipboard::{SelectionError, SelectionRead};
use crate::selection::SELECTION_LIMIT;
use crate::wayland_state::State;
use rustix::event::{PollFd, PollFlags, Timespec, poll};
use wayland_client::backend::WaylandError;
use wayland_client::protocol::wl_seat::WlSeat;
use wayland_client::{ConnectError, Connection, DispatchError, EventQueue};
use wayland_protocols::ext::data_control::v1::client::ext_data_control_manager_v1::ExtDataControlManagerV1;
use wayland_protocols_wlr::data_control::v1::client::zwlr_data_control_manager_v1::ZwlrDataControlManagerV1;

/// The most bytes one read from the owner's pipe takes.
const CHUNK: usize = 65_536;

/// A compositor connection the clipboard is read through, or one that could not be opened.
///
/// Each read binds its own objects, which live until the connection closes, so the shell opens
/// one connection per paste.
pub struct WaylandSelection {
    connection: Result<Connection, SelectionError>,
    limit: Duration,
}

impl WaylandSelection {
    /// Reads through `connection`, waiting [`SELECTION_LIMIT`] for each answer.
    #[must_use]
    pub const fn new(connection: Connection) -> Self {
        Self::with_limit(connection, SELECTION_LIMIT)
    }

    /// As [`WaylandSelection::new`], waiting `limit` for each answer instead.
    #[must_use]
    pub const fn with_limit(connection: Connection, limit: Duration) -> Self {
        Self {
            connection: Ok(connection),
            limit,
        }
    }

    /// Stands in for a compositor that could not be reached: every read fails with `error`'s text.
    #[must_use]
    pub fn absent(error: &ConnectError) -> Self {
        Self {
            connection: Err(SelectionError::Failed(error.to_string())),
            limit: SELECTION_LIMIT,
        }
    }
}

impl SelectionRead for WaylandSelection {
    fn offered(&self) -> Result<Vec<String>, SelectionError> {
        let connection = self.connection.as_ref().map_err(Clone::clone)?;
        let (_, mut state) = listen(connection)?;
        Ok(state
            .take_selection()
            .map(|(_, types)| types)
            .unwrap_or_default())
    }

    fn convert(&self, target: &str, limit: usize) -> Result<Option<Vec<u8>>, SelectionError> {
        let connection = self.connection.as_ref().map_err(Clone::clone)?;
        let (mut queue, mut state) = listen(connection)?;
        let Some((offer, _)) = state.take_selection() else {
            return Ok(None);
        };
        let piped = io::pipe().map_err(WaylandError::Io);
        // The round trip has the compositor pass the pipe on before the read waits on it.
        let reader = piped
            .map_err(DispatchError::Backend)
            .and_then(|(reader, writer)| {
                offer.receive(target, writer.as_fd());
                drop(writer);
                queue.roundtrip(&mut state).map(|_| reader)
            })?;
        drain(&reader, limit, self.limit).map(Some)
    }
}

impl From<DispatchError> for SelectionError {
    fn from(error: DispatchError) -> Self {
        Self::Failed(error.to_string())
    }
}

/// Binds the seat's data control device, and returns once the compositor has sent its selection.
fn listen(connection: &Connection) -> Result<(EventQueue<State>, State), SelectionError> {
    let mut queue = connection.new_event_queue();
    let handle = queue.handle();
    let registry = connection.display().get_registry(&handle, ());
    let mut state = State::default();
    queue.roundtrip(&mut state)?;
    let seat = state
        .global("wl_seat")
        .ok_or_else(|| SelectionError::Failed(String::from("the compositor lists no seat")))?;
    let seat: WlSeat = registry.bind(seat, 1, &handle, ());
    if let Some(name) = state.global("ext_data_control_manager_v1") {
        let manager: ExtDataControlManagerV1 = registry.bind(name, 1, &handle, ());
        manager.get_data_device(&seat, &handle, ());
    } else if let Some(name) = state.global("zwlr_data_control_manager_v1") {
        let manager: ZwlrDataControlManagerV1 = registry.bind(name, 1, &handle, ());
        manager.get_data_device(&seat, &handle, ());
    } else {
        let reason = "the compositor offers no data control protocol";
        return Err(SelectionError::Failed(String::from(reason)));
    }
    queue.roundtrip(&mut state)?;
    Ok((queue, state))
}

/// Reads `reader` to its end, failing past `limit` bytes or once `patience` passes with nothing.
fn drain(
    mut reader: &PipeReader,
    limit: usize,
    patience: Duration,
) -> Result<Vec<u8>, SelectionError> {
    let mut data = Vec::new();
    let mut chunk = vec![0; CHUNK];
    let wait = Timespec {
        tv_sec: i64::try_from(patience.as_secs()).unwrap_or(i64::MAX),
        tv_nsec: i64::from(patience.subsec_nanos()),
    };
    loop {
        let mut watched = [PollFd::new(reader, PollFlags::IN)];
        // A failed wait or read on the pipe counts as no answer, as a wait that ran out does.
        let ready = poll(&mut watched, Some(&wait))
            .ok()
            .filter(|&ready| ready > 0);
        let Some(read) = ready.and_then(|_| reader.read(&mut chunk).ok()) else {
            return Err(SelectionError::Silent);
        };
        if read == 0 {
            return Ok(data);
        }
        if data.len() + read > limit {
            return Err(SelectionError::Over);
        }
        data.extend_from_slice(&chunk[..read]);
    }
}
