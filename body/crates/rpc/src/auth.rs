//! The body-side token validator: the server mirror of the client interceptor.
//!
//! It rejects any `BodyService` call without the shared `x-cortex-seam-token` metadata, before
//! any handler runs, and passes every call through when the configured token is empty.

use tonic::metadata::MetadataValue;
use tonic::service::Interceptor;
use tonic::{Request, Status};

/// The metadata key the shared token travels under. The brain declares the same key.
const SEAM_TOKEN_HEADER: &str = "x-cortex-seam-token";

/// Validates the shared token on inbound `BodyService` calls. It must not derive `Debug`,
/// because it holds the secret.
#[derive(Clone)]
pub struct SeamTokenValidator {
    /// The expected token bytes, or `None` when auth is disabled (empty token = pass-through).
    token: Option<Vec<u8>>,
}

impl SeamTokenValidator {
    /// Builds the validator; an empty `token` disables the check (a tokenless server).
    #[must_use]
    pub fn new(token: &str) -> Self {
        let token = if token.is_empty() {
            None
        } else {
            Some(token.as_bytes().to_vec())
        };
        Self { token }
    }
}

impl Interceptor for SeamTokenValidator {
    fn call(&mut self, request: Request<()>) -> Result<Request<()>, Status> {
        let Some(expected) = &self.token else {
            return Ok(request);
        };
        let presented = request
            .metadata()
            .get(SEAM_TOKEN_HEADER)
            .map(MetadataValue::as_encoded_bytes);
        match presented {
            Some(value) if constant_time_eq(value, expected) => Ok(request),
            _ => Err(Status::unauthenticated("invalid or missing seam token")),
        }
    }
}

/// Fixed-time byte comparison, the Rust equivalent of `secrets.compare_digest`. Equal-length
/// inputs are compared in full, so the time taken does not reveal how much of the token matched.
fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut diff = 0u8;
    for (x, y) in a.iter().zip(b) {
        diff |= x ^ y;
    }
    diff == 0
}
