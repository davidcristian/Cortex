//! The tonic adapter for the body to brain gRPC interface defined in `proto/body.proto`.
//!
//! It holds the committed stubs, [`BrainRpcClient`] behind the `body_core::BrainTransport`
//! port, and [`body_service`], the server the brain calls. No business logic lives here.

mod auth;
mod call;
mod client;
mod converse;
mod preferences;
mod reminders;
mod screen;
mod server;
mod sessions;
mod status;

/// Generated tonic/prost stubs for the `cortex.seam.v1` package. Public because the contract
/// tests drive the generated server and client directly.
pub mod generated {
    #![allow(
        clippy::all,
        clippy::pedantic,
        clippy::nursery,
        clippy::unwrap_used,
        clippy::expect_used
    )]

    include!("_generated/cortex.seam.v1.rs");
}

pub use auth::RpcTokenValidator;
pub use client::BrainRpcClient;
pub use server::{OsService, body_service};
pub use status::status_to_error;
