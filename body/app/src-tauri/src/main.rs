// The Cortex body binary. Release builds on Windows hide the console window; all
// real logic lives in the library crate (thin `main`, ADR-0011 decision 5).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    cortex_body_lib::run();
}
