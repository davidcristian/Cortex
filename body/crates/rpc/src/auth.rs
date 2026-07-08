//! The body-side seam-token validator: the server mirror of the client interceptor (ADR-0016,
//! reversed for the brain→body direction by ADR-0023).
//!
//! Rejects any `BodyService` call not bearing the shared `x-cortex-seam-token` metadata with
//! `UNAUTHENTICATED`, before any handler runs. This is the structural check the brain's Python
//! `SeamTokenInterceptor` does for the other direction. It is **always attached** but a
//! **pass-through when the configured token is empty** (a tokenless deployment is unchanged),
//! the single-type equivalent of the brain's register-only-when-set. The compare is
//! constant-time, matching `secrets.compare_digest`.

use tonic::metadata::MetadataValue;
use tonic::service::Interceptor;
use tonic::{Request, Status};

/// The metadata key the seam token travels under (ADR-0016; lowercase per gRPC). The brain's
/// `cortex_seam.SEAM_TOKEN_HEADER` carries the same value on the Python side.
const SEAM_TOKEN_HEADER: &str = "x-cortex-seam-token";

/// Validates the seam token on inbound `BodyService` calls. Deliberately NOT `Debug`: it holds
/// the shared secret (mirrors the client `SeamTokenInterceptor`).
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

/// Fixed-time byte comparison (the Rust twin of `secrets.compare_digest`): unequal lengths fail
/// fast, but equal-length inputs are compared in full so the time taken does not leak how much
/// of the token matched.
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
