use std::ffi::OsString;
use std::io::Read;
use std::path::{Path, PathBuf};

#[cfg(unix)]
use std::os::unix::ffi::OsStringExt;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::pybacked::PyBackedBytes;
use pyo3::types::PyBytes;

use crate::inventory::{
    JSONL_SCAN_CHUNK_SIZE, LineVerdict, Provider, discover_session_files_impl,
    os_string_bytes, trim_python_byte_whitespace,
};
use crate::scanner::{
    file_contains_ascii_impl, file_contains_ascii_json_strings_impl,
    files_contain_ascii_json_strings_impl,
};

/// Ask Python for one line's timestamp, mirroring the legacy line decoder.
///
/// The trim lives here rather than in the shared walk because this caller needs
/// Python's four-byte JSON whitespace set specifically.
fn timestamp_from_line(
    py: Python<'_>,
    line: &[u8],
    line_timestamp: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
) -> LineVerdict<Py<PyAny>> {
    let line = trim_python_byte_whitespace(line);
    if line.is_empty() {
        return LineVerdict::Continue;
    }
    let Ok(decoded_line) = std::str::from_utf8(line) else {
        return LineVerdict::Continue;
    };
    let timestamp = match line_timestamp.call1((decoded_line,)) {
        Ok(timestamp) => timestamp,
        Err(error) if error.is_instance(py, json_decode_error) => {
            return LineVerdict::Continue;
        }
        Err(_) => return LineVerdict::Abort,
    };
    if timestamp.is_none() {
        return LineVerdict::Continue;
    }
    LineVerdict::Found(timestamp.unbind())
}

const RESOLUTION_FACET_MARKERS: [&str; 4] = [
    "\"summary\"",
    "\"custom-title\"",
    "\"session_info\"",
    "\"thread_name_updated\"",
];

fn accumulate_resolution_line(
    py: Python<'_>,
    line: &[u8],
    line_facets: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
    latest_title: &mut Option<Py<PyAny>>,
    summaries: &mut Vec<Py<PyAny>>,
) -> PyResult<()> {
    let decoded_line = match std::str::from_utf8(line) {
        Ok(decoded_line) => decoded_line,
        Err(_) => {
            PyBytes::new(py, line).call_method1("decode", ("utf-8",))?;
            unreachable!("invalid UTF-8 decode must raise")
        }
    };
    if !RESOLUTION_FACET_MARKERS
        .iter()
        .any(|marker| decoded_line.contains(marker))
    {
        return Ok(());
    }

    let facets = match line_facets.call1((decoded_line,)) {
        Ok(facets) => facets,
        Err(error) if error.is_instance(py, json_decode_error) => return Ok(()),
        Err(error) => return Err(error),
    };
    let (title, summary): (Option<Py<PyAny>>, Option<Py<PyAny>>) = facets.extract()?;
    if title.is_some() {
        *latest_title = title;
    }
    if let Some(summary) = summary {
        summaries.push(summary);
    }
    Ok(())
}

fn scan_resolution_facets_impl(
    py: Python<'_>,
    path: &Path,
    line_facets: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
) -> PyResult<(Option<Py<PyAny>>, Vec<Py<PyAny>>)> {
    let mut file = match std::fs::File::open(path) {
        Ok(file) => file,
        Err(_) => return Ok((None, Vec::new())),
    };
    let mut latest_title = None;
    let mut summaries = Vec::new();
    let mut line = Vec::new();
    let mut block = [0; JSONL_SCAN_CHUNK_SIZE];
    let mut skip_leading_line_feed = false;

    loop {
        let read_size = match file.read(&mut block) {
            Ok(read_size) => read_size,
            Err(_) => return Ok((None, Vec::new())),
        };
        if read_size == 0 {
            break;
        }

        let mut cursor = usize::from(skip_leading_line_feed && block[0] == b'\n');
        skip_leading_line_feed = false;
        while cursor < read_size {
            let Some(relative_delimiter) = block[cursor..read_size]
                .iter()
                .position(|byte| matches!(*byte, b'\r' | b'\n'))
            else {
                line.extend_from_slice(&block[cursor..read_size]);
                break;
            };
            let delimiter = cursor + relative_delimiter;
            line.extend_from_slice(&block[cursor..delimiter]);
            accumulate_resolution_line(
                py,
                &line,
                line_facets,
                json_decode_error,
                &mut latest_title,
                &mut summaries,
            )?;
            line.clear();

            cursor = delimiter + 1;
            if block[delimiter] != b'\r' {
                continue;
            }
            if cursor == read_size {
                skip_leading_line_feed = true;
                continue;
            }
            if block[cursor] == b'\n' {
                cursor += 1;
            }
        }
    }

    if !line.is_empty() {
        accumulate_resolution_line(
            py,
            &line,
            line_facets,
            json_decode_error,
            &mut latest_title,
            &mut summaries,
        )?;
    }
    Ok((latest_title, summaries))
}

#[pyfunction]
fn file_contains_ascii(
    path: PyBackedBytes,
    needle: PyBackedBytes,
    case_sensitive: bool,
    evidence_groups: Vec<Vec<PyBackedBytes>>,
) -> PyResult<bool> {
    Ok(file_contains_ascii_impl(
        &path_from_python_bytes(path.as_ref()),
        needle.as_ref(),
        case_sensitive,
        &owned_evidence_groups(evidence_groups),
    )?)
}

fn owned_evidence_groups(evidence_groups: Vec<Vec<PyBackedBytes>>) -> Vec<Vec<Vec<u8>>> {
    evidence_groups
        .into_iter()
        .map(|group| {
            group
                .into_iter()
                .map(|evidence| evidence.as_ref().to_vec())
                .collect()
        })
        .collect()
}

#[cfg(unix)]
fn path_from_python_bytes(path: &[u8]) -> PathBuf {
    PathBuf::from(OsString::from_vec(path.to_vec()))
}

#[cfg(not(unix))]
fn path_from_python_bytes(path: &[u8]) -> PathBuf {
    PathBuf::from(String::from_utf8_lossy(path).into_owned())
}

#[pyfunction]
fn file_contains_ascii_json_strings(
    path: PyBackedBytes,
    needle: PyBackedBytes,
    evidence_groups: Vec<Vec<PyBackedBytes>>,
) -> PyResult<bool> {
    Ok(file_contains_ascii_json_strings_impl(
        &path_from_python_bytes(path.as_ref()),
        needle.as_ref(),
        &owned_evidence_groups(evidence_groups),
    )?)
}

#[pyfunction]
fn files_contain_ascii_json_strings(
    paths: Vec<PyBackedBytes>,
    needle: PyBackedBytes,
    pi_sessions: Vec<bool>,
) -> PyResult<Vec<bool>> {
    if paths.len() != pi_sessions.len() {
        return Err(PyValueError::new_err(
            "paths and pi_sessions must have equal lengths",
        ));
    }
    let paths = paths
        .into_iter()
        .map(|path| path_from_python_bytes(path.as_ref()))
        .collect::<Vec<_>>();
    Ok(files_contain_ascii_json_strings_impl(
        paths,
        needle.as_ref(),
        pi_sessions,
    ))
}

#[pyfunction]
fn classify_native_session_path(path: &str, home: &str) -> Option<&'static str> {
    crate::inventory::classify_native_session_path_impl(
        std::path::Path::new(path),
        std::path::Path::new(home),
    )
    .map(Provider::as_str)
}

#[pyfunction]
fn find_last_jsonl_timestamp(
    py: Python<'_>,
    path: &str,
    line_timestamp: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
) -> Option<Py<PyAny>> {
    crate::inventory::for_each_line_backward(std::path::Path::new(path), |line| {
        timestamp_from_line(py, line, line_timestamp, json_decode_error)
    })
}

#[pyfunction]
fn scan_resolution_facets(
    py: Python<'_>,
    path: &Bound<'_, PyBytes>,
    line_facets: &Bound<'_, PyAny>,
    json_decode_error: &Bound<'_, PyAny>,
) -> PyResult<(Option<Py<PyAny>>, Vec<Py<PyAny>>)> {
    scan_resolution_facets_impl(
        py,
        &path_from_python_bytes(path.as_bytes()),
        line_facets,
        json_decode_error,
    )
}

#[pyfunction]
fn discover_session_files(
    py: Python<'_>,
    home: &Bound<'_, PyBytes>,
    include_sidechains: bool,
) -> Vec<(Py<PyBytes>, Option<&'static str>, f64)> {
    discover_session_files_impl(&path_from_python_bytes(home.as_bytes()), include_sidechains)
        .into_iter()
        .map(|(path, provider, mtime)| {
            let path = PyBytes::new(py, os_string_bytes(path.as_os_str())).unbind();
            (path, provider.map(Provider::as_str), mtime)
        })
        .collect()
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(file_contains_ascii, module)?)?;
    module.add_function(wrap_pyfunction!(file_contains_ascii_json_strings, module)?)?;
    module.add_function(wrap_pyfunction!(files_contain_ascii_json_strings, module)?)?;
    module.add_function(wrap_pyfunction!(classify_native_session_path, module)?)?;
    module.add_function(wrap_pyfunction!(find_last_jsonl_timestamp, module)?)?;
    module.add_function(wrap_pyfunction!(scan_resolution_facets, module)?)?;
    module.add_function(wrap_pyfunction!(discover_session_files, module)?)
}
