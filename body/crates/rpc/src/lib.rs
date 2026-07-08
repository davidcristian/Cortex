//! tonic adapter for the body↔brain gRPC seam (`proto/body.proto`).

mod auth;
mod client;
mod converse;
mod server;
mod sessions;
mod status;

/// Generated tonic/prost stubs for the `cortex.seam.v1` package.
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

pub use auth::SeamTokenValidator;
pub use client::BrainSeamClient;
pub use server::{VolumeService, body_service};
