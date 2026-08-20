pub mod codecs;
pub mod model;

#[cfg(any(feature = "python-bindings", feature = "extension-module"))]
include!("python_extension.rs");
