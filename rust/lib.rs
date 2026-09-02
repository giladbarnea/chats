pub mod clock;
pub mod color;
pub mod difflib;
pub mod cell_tables;
pub mod cells;
pub mod codecs;
pub mod codex;
pub mod inventory;
pub mod scanner;
pub mod model;
pub mod pager;
pub mod raw_transcript;
pub mod pool_filter;
pub mod python_io;
pub mod search;
pub mod search_confirm;
pub mod search_engine;
pub mod search_output;
pub mod search_query;
pub mod search_run;
pub mod search_views;
pub mod session;
pub mod session_pool;
pub mod session_render;
pub mod syntax_json;
pub mod syntax_lexer;
pub mod syntax_lexers;
pub mod syntax_styles;
pub mod syntax_tables;
#[cfg(test)]
mod syntax_table_gates;
pub mod shortening;
pub mod terminal;
pub mod tool_filter;
pub mod visibility;
#[cfg(test)]
mod wrap_gates;

#[cfg(any(feature = "python-bindings", feature = "extension-module"))]
include!("python_extension.rs");
