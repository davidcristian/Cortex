//! Env-gated regeneration of the committed seam stubs (`src/_generated/`).
//!
//! Normal builds (including CI) do nothing: the stubs generated from
//! `proto/body.proto` are committed, so neither `protoc` nor codegen runs.
//! Set `CORTEX_REGEN_PROTO=1` (with `protoc` on PATH) to regenerate them, and
//! see `docs/modules/body-rpc.md`.

use std::env;
use std::error::Error;
use std::fs;

const PROTO_FILE: &str = "../../../proto/body.proto";
const PROTO_DIR: &str = "../../../proto";
const OUT_DIR: &str = "src/_generated";

fn main() -> Result<(), Box<dyn Error>> {
    println!("cargo:rerun-if-env-changed=CORTEX_REGEN_PROTO");
    println!("cargo:rerun-if-changed={PROTO_FILE}");
    // Watch the output too, so a deleted or hand-edited stub re-triggers this
    // script (which regenerates only when CORTEX_REGEN_PROTO=1).
    println!("cargo:rerun-if-changed={OUT_DIR}");
    if env::var("CORTEX_REGEN_PROTO").as_deref() != Ok("1") {
        return Ok(());
    }
    fs::create_dir_all(OUT_DIR)?;
    tonic_prost_build::configure()
        .out_dir(OUT_DIR)
        .compile_protos(&[PROTO_FILE], &[PROTO_DIR])?;
    Ok(())
}
