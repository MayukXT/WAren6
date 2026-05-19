fn main() {
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        println!("cargo:rustc-link-arg-bin=waren6-reader=/STACK:16777216");
    }
    tauri_build::build()
}
