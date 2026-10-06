//! `FakeClipboard`, the stand-in `ClipboardPicture` backend held to the shared check list.

use body_core::{ClipboardError, ClipboardPicture, MAX_PASTED_BYTES, PICTURE_TYPES, PastedPicture};

use crate::clipboard::Offer;

/// A `ClipboardPicture` whose owner offers a fixed list of types, or that fails every read.
pub struct FakeClipboard {
    offers: Result<Vec<Offer>, ClipboardError>,
}

impl FakeClipboard {
    /// A clipboard whose owner offers `offers`.
    #[must_use]
    pub const fn offering(offers: Vec<Offer>) -> Self {
        Self { offers: Ok(offers) }
    }

    /// A clipboard that answers every read with `error`.
    #[must_use]
    pub const fn failing(error: ClipboardError) -> Self {
        Self { offers: Err(error) }
    }
}

impl ClipboardPicture for FakeClipboard {
    fn picture(&self) -> Result<Option<PastedPicture>, ClipboardError> {
        let offers = self.offers.as_ref().map_err(Clone::clone)?;
        let first = PICTURE_TYPES.into_iter().find_map(|wanted| {
            offers
                .iter()
                .find(|(offered, data)| *offered == wanted && !data.is_empty())
                .map(|(_, data)| (wanted, data))
        });
        match first {
            Some((_, data)) if data.len() > MAX_PASTED_BYTES => Err(ClipboardError::TooLarge),
            Some((mime_type, data)) => Ok(Some(PastedPicture {
                data: data.clone(),
                mime_type,
            })),
            None => Ok(None),
        }
    }
}
