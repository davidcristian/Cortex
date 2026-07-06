//! tonic adapter for the body↔brain gRPC seam (`proto/body.proto`).

mod client;
mod converse;
mod sessions;

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

pub use client::BrainSeamClient;
