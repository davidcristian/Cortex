//! Preference-record translation for `BrainSeamClient`, the settings half of the
//! `body_core::BrainTransport` port.
//!
//! The user's settings live in the brain so a choice outlives the window that made it: the
//! overlay reads the record once at startup and writes one pair per change. Thin translation
//! only, exactly as [`crate::sessions`] does it: map the request, await the unary reply, map the
//! rows to plain pairs, and let a non-OK gRPC status become a [`TransportError`] through
//! [`crate::status::status_to_error`]. A brain with no preference store answers an empty record
//! and accepts a write silently rather than a status, so nothing here special-cases it.

use body_core::TransportError;

use crate::client::SeamChannel;
use crate::generated::brain_service_client::BrainServiceClient;
use crate::generated::{GetPreferencesRequest, SetPreferenceRequest};
use crate::status::status_to_error;

/// Reads every stored setting (`BrainService.GetPreferences`). Values are opaque to this layer:
/// it hands the caller the pairs verbatim, in the order the brain sorted them.
pub(crate) async fn get_preferences(
    mut client: BrainServiceClient<SeamChannel>,
) -> Result<Vec<(String, String)>, TransportError> {
    let reply = client
        .get_preferences(GetPreferencesRequest {})
        .await
        .map_err(|status| status_to_error(&status))?
        .into_inner();
    Ok(reply
        .preferences
        .into_iter()
        .map(|preference| (preference.key, preference.value))
        .collect())
}

/// Writes one setting (`BrainService.SetPreference`). An empty `value` clears the key, which the
/// brain applies; this side only carries it. The reply is a bare acknowledgement, so on success
/// there is nothing to map back.
pub(crate) async fn set_preference(
    mut client: BrainServiceClient<SeamChannel>,
    key: String,
    value: String,
) -> Result<(), TransportError> {
    client
        .set_preference(SetPreferenceRequest { key, value })
        .await
        .map_err(|status| status_to_error(&status))?;
    Ok(())
}
