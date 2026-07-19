//! The preference commands the overlay calls: the user's settings record, held by the brain.

use body_core::BrainTransport;

/// Reads the whole settings record (`BrainService.GetPreferences`).
#[tauri::command]
pub async fn get_preferences() -> Result<Vec<(String, String)>, String> {
    let client = crate::seam::connect()?;
    client
        .get_preferences()
        .await
        .map_err(|error| error.to_string())
}

/// Writes one setting (`BrainService.SetPreference`): `key` is a namespaced name the overlay owns,
/// and an empty `value` clears it so the default applies again.
#[tauri::command]
pub async fn set_preference(key: String, value: String) -> Result<(), String> {
    let client = crate::seam::connect()?;
    client
        .set_preference(&key, &value)
        .await
        .map_err(|error| error.to_string())
}
