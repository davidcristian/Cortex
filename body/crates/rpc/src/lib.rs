//! tonic adapter for the body↔brain gRPC seam (`proto/body.proto`).
//!
//! This crate is a thin adapter: it holds the committed tonic/prost stubs
//! generated from the proto (the seam's single source of truth, AGENTS.md),
//! [`BrainSeamClient`] (the body→brain `BrainService` client behind the
//! `body_core::BrainTransport` port), and [`body_service`] (the brain→body
//! `BodyService` server over the `body_core::AudioControl` port, Slice 9,
//! ADR-0023). No business logic lives here.

mod auth;
mod client;
mod converse;
mod reminders;
mod server;
mod sessions;
mod status;

/// Generated tonic/prost stubs for the `cortex.seam.v1` package.
///
/// The inner file is produced by `tonic-prost-build` (see `build.rs`; regen
/// with `CORTEX_REGEN_PROTO=1`) and committed under `src/_generated/`, the
/// repo's generated-code marker (ADR-0002 decision 4): exempt from the line
/// cap, coverage, and (via these allows) the clippy gate. Public because
/// contract tests drive the generated `BrainService` server/client directly.
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
