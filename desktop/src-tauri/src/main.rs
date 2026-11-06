// Hides the extra console window on Windows in release builds. DO NOT REMOVE!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    uninv_desktop_lib::run()
}
