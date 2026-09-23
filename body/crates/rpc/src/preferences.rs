//! Preference-record translation for `BrainRpcClient`, the settings half of the
//! `body_core::BrainTransport` port.

use body_core::TransportError;

use crate::call::RpcCall;
use crate::generated::{GetPreferencesRequest, SetPreferenceRequest};

/// Reads every stored setting (`BrainService.GetPreferences`).
pub(crate) async fn get_preferences(
    call: RpcCall,
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
    call: RpcCall,
    key: String,
    value: String,
) -> Result<(), TransportError> {
    call.client()
        .set_preference(SetPreferenceRequest { key, value })
        .await
        .map_err(|status| call.error(&status))?;
    Ok(())
}
