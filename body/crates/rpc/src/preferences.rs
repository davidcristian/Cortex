//! Preference-record translation for `BrainSeamClient`, the settings half of the
//! `body_core::BrainTransport` port.
//!
//! The user's settings live in the brain so a choice outlives the window that made it: the
//! overlay reads the record once at startup and writes one pair per change. Thin translation
//! only, exactly as [`crate::sessions`] does it: map the request, await the unary reply, map the
//! rows to plain pairs, and let a non-OK gRPC status become a [`TransportError`] through the
//! [`SeamCall`] the client hands in. A brain with no preference store answers an empty record
//! and accepts a write silently rather than a status, so nothing here special-cases it.

use body_core::TransportError;

use crate::call::SeamCall;
use crate::generated::{GetPreferencesRequest, SetPreferenceRequest};

/// Reads every stored setting (`BrainService.GetPreferences`). Values are opaque to this layer:
/// it hands the caller the pairs verbatim, in the order the brain sorted them.
pub(crate) async fn get_preferences(
    call: SeamCall,
) -> Result<Vec<(String, String)>, TransportError> {
    let mut client = call.client();
    let reply = client
        .get_preferences(GetPreferencesRequest {})
        .await
        .map_err(|status| call.error(&status))?
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
    call: SeamCall,
    key: String,
    value: String,
) -> Result<(), TransportError> {
    call.client()
        .set_preference(SetPreferenceRequest { key, value })
        .await
        .map_err(|status| call.error(&status))?;
    Ok(())
}
