//! The Wayland objects one clipboard read binds, and what their events tell it.

use std::collections::HashMap;
use std::os::fd::BorrowedFd;
use std::sync::Arc;

use wayland_client::backend::{ObjectData, ObjectId};
use wayland_client::protocol::wl_registry::{self, WlRegistry};
use wayland_client::protocol::wl_seat::{self, WlSeat};
use wayland_client::{Connection, Dispatch, Proxy, QueueHandle};
use wayland_protocols::ext::data_control::v1::client::ext_data_control_device_v1::{
    self as ext_device, ExtDataControlDeviceV1,
};
use wayland_protocols::ext::data_control::v1::client::ext_data_control_manager_v1::{
    self as ext_manager, ExtDataControlManagerV1,
};
use wayland_protocols::ext::data_control::v1::client::ext_data_control_offer_v1::{
    self as ext_offer, ExtDataControlOfferV1,
};
use wayland_protocols_wlr::data_control::v1::client::zwlr_data_control_device_v1::{
    self as wlr_device, ZwlrDataControlDeviceV1,
};
use wayland_protocols_wlr::data_control::v1::client::zwlr_data_control_manager_v1::{
    self as wlr_manager, ZwlrDataControlManagerV1,
};
use wayland_protocols_wlr::data_control::v1::client::zwlr_data_control_offer_v1::{
    self as wlr_offer, ZwlrDataControlOfferV1,
};

/// The selection's offer under the protocol the compositor was read through.
pub enum Offer {
    Ext(ExtDataControlOfferV1),
    Wlr(ZwlrDataControlOfferV1),
}

impl Offer {
    /// Asks the owner to write the selection as `target` to `pipe`.
    pub fn receive(&self, target: &str, pipe: BorrowedFd<'_>) {
        match self {
            Self::Ext(offer) => offer.receive(target.to_owned(), pipe),
            Self::Wlr(offer) => offer.receive(target.to_owned(), pipe),
        }
    }
}

/// A device or offer event under either protocol, with the offer it names.
enum Heard {
    ExtDevice(ext_device::Event),
    WlrDevice(wlr_device::Event),
    ExtOffer(ObjectId, ext_offer::Event),
    WlrOffer(ObjectId, wlr_offer::Event),
}

/// What one read has heard from the compositor.
#[derive(Default)]
pub struct State {
    globals: Vec<(u32, String)>,
    types: HashMap<ObjectId, Vec<String>>,
    selection: Option<Offer>,
}

impl State {
    /// The registry name of the first global with `interface`.
    pub fn global(&self, interface: &str) -> Option<u32> {
        let mut named = self
            .globals
            .iter()
            .filter(|(_, listed)| listed == interface);
        named.next().map(|(name, _)| *name)
    }

    /// The selection's offer and the types it lists, `None` when nothing is selected.
    pub fn take_selection(&mut self) -> Option<(Offer, Vec<String>)> {
        let offer = self.selection.take()?;
        let id = match &offer {
            Offer::Ext(offer) => offer.id(),
            Offer::Wlr(offer) => offer.id(),
        };
        let types = self.types.remove(&id).unwrap_or_default();
        Some((offer, types))
    }

    fn heard(&mut self, event: Heard) {
        match event {
            Heard::ExtDevice(ext_device::Event::Selection { id }) => {
                self.selection = id.map(Offer::Ext);
            }
            Heard::WlrDevice(wlr_device::Event::Selection { id }) => {
                self.selection = id.map(Offer::Wlr);
            }
            Heard::ExtOffer(offer, ext_offer::Event::Offer { mime_type })
            | Heard::WlrOffer(offer, wlr_offer::Event::Offer { mime_type }) => {
                self.types.entry(offer).or_default().push(mime_type);
            }
            // `data_offer`, `finished` and `primary_selection` change nothing a read keeps.
            _ => {}
        }
    }
}

impl Dispatch<WlRegistry, ()> for State {
    fn event(
        state: &mut Self,
        _: &WlRegistry,
        event: wl_registry::Event,
        (): &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
        if let wl_registry::Event::Global {
            name, interface, ..
        } = event
        {
            state.globals.push((name, interface));
        }
    }
}

impl Dispatch<WlSeat, ()> for State {
    fn event(
        _: &mut Self,
        _: &WlSeat,
        _: wl_seat::Event,
        (): &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
    }
}

impl Dispatch<ExtDataControlManagerV1, ()> for State {
    // The manager interface has no events.
    #[cfg_attr(coverage, coverage(off))]
    fn event(
        _: &mut Self,
        _: &ExtDataControlManagerV1,
        _: ext_manager::Event,
        (): &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
    }
}

impl Dispatch<ZwlrDataControlManagerV1, ()> for State {
    // The manager interface has no events.
    #[cfg_attr(coverage, coverage(off))]
    fn event(
        _: &mut Self,
        _: &ZwlrDataControlManagerV1,
        _: wlr_manager::Event,
        (): &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
    }
}

impl Dispatch<ExtDataControlDeviceV1, ()> for State {
    fn event(
        state: &mut Self,
        _: &ExtDataControlDeviceV1,
        event: ext_device::Event,
        (): &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
        state.heard(Heard::ExtDevice(event));
    }

    // `data_offer` is the device's one event that creates an object.
    fn event_created_child(_: u16, handle: &QueueHandle<Self>) -> Arc<dyn ObjectData> {
        handle.make_data::<ExtDataControlOfferV1, _>(())
    }
}

impl Dispatch<ZwlrDataControlDeviceV1, ()> for State {
    fn event(
        state: &mut Self,
        _: &ZwlrDataControlDeviceV1,
        event: wlr_device::Event,
        (): &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
        state.heard(Heard::WlrDevice(event));
    }

    // `data_offer` is the device's one event that creates an object.
    fn event_created_child(_: u16, handle: &QueueHandle<Self>) -> Arc<dyn ObjectData> {
        handle.make_data::<ZwlrDataControlOfferV1, _>(())
    }
}

impl Dispatch<ExtDataControlOfferV1, ()> for State {
    fn event(
        state: &mut Self,
        offer: &ExtDataControlOfferV1,
        event: ext_offer::Event,
        (): &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
        state.heard(Heard::ExtOffer(offer.id(), event));
    }
}

impl Dispatch<ZwlrDataControlOfferV1, ()> for State {
    fn event(
        state: &mut Self,
        offer: &ZwlrDataControlOfferV1,
        event: wlr_offer::Event,
        (): &(),
        _: &Connection,
        _: &QueueHandle<Self>,
    ) {
        state.heard(Heard::WlrOffer(offer.id(), event));
    }
}
