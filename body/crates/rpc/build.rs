//! Regenerates the committed gRPC stubs in `src/_generated/` when `CORTEX_REGEN_PROTO` is set.

use std::env;
use std::error::Error;
use std::fs;

const PROTO_FILE: &str = "../../../proto/body.proto";
const PROTO_DIR: &str = "../../../proto";
const OUT_DIR: &str = "src/_generated";

fn main() -> Result<(), Box<dyn Error>> {
    println!("cargo:rerun-if-env-changed=CORTEX_REGEN_PROTO");
    println!("cargo:rerun-if-changed={PROTO_FILE}");
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
