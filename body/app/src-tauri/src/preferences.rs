//! The preference commands the overlay calls: the user's settings record, held by the brain.
//!
//! Thin glue in the ungated shell, exactly as [`crate::sessions`] is: connect, call the port,
//! map the error to a string the JS bridge rejects with. No policy lives here; which keys exist
//! and what their values mean is the overlay's business, and where they are stored is the
//! brain's.

use body_core::BrainTransport;

/// Reads the whole settings record (`BrainService.GetPreferences`). The overlay asks once at
/// startup and applies the keys it recognises, so pairs cross as `(key, value)` tuples with the
/// values still opaque. An empty record is the normal first-run answer, never an error. A read,
/// so the resilient transport retries it like the other reads.
#[tauri::command]
pub async fn get_preferences() -> Result<Vec<(String, String)>, String> {
    let client = crate::seam::connect()?;
    client
        .get_preferences()
        .await
        .map_err(|error| error.to_string())
}

/// Writes one setting (`BrainService.SetPreference`): `key` is a namespaced name the overlay
/// owns, and an empty `value` clears it so the default applies again. A write, so the resilient
/// transport makes exactly one attempt (`SeamMethod::SetPreference` is not repeatable); a
/// transient failure surfaces to the overlay bridge's `.catch`, where the choice stays applied
/// for the session rather than being rolled back under the user.
#[tauri::command]
pub async fn set_preference(key: String, value: String) -> Result<(), String> {
    let client = crate::seam::connect()?;
    client
        .set_preference(&key, &value)
        .await
        .map_err(|error| error.to_string())
}
