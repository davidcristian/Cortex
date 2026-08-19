//! Preference-record translation for `BrainSeamClient`, the settings half of the
//! `body_core::BrainTransport` port.

use body_core::TransportError;

use crate::call::SeamCall;
use crate::generated::{GetPreferencesRequest, SetPreferenceRequest};

/// Reads every stored setting (`BrainService.GetPreferences`).
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

/// Writes one setting (`BrainService.SetPreference`).
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
