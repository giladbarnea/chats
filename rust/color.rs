//! Rich's colour downgrade, and how much of a style a terminal keeps.
//!
//! Every style the product emits is authored in truecolor. Rich downgrades it to
//! whatever the terminal actually supports before writing bytes.
//! [`terminal::resolve_color`](crate::terminal::resolve_color) decides *which*
//! system applies; this module applies it.

use crate::terminal::{ColorSystem, TerminalCapabilities};

/// The red, green and blue components of a colour, mirroring Rich's `ColorTriplet`.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ColorTriplet {
    pub red: u8,
    pub green: u8,
    pub blue: u8,
}

impl ColorTriplet {
    /// Build a triplet from the `#rrggbb` form the theme is written in.
    ///
    /// ```
    /// use _native::color::ColorTriplet;
    /// let teal = ColorTriplet::from_hex("#5cc8a8");
    /// assert_eq!((teal.red, teal.green, teal.blue), (92, 200, 168));
    /// ```
    pub const fn from_hex(hex: &str) -> ColorTriplet {
        let bytes = hex.as_bytes();
        assert!(
            bytes.len() == 7 && bytes[0] == b'#',
            "a theme colour is written as #rrggbb"
        );
        ColorTriplet {
            red: hex_byte(bytes[1], bytes[2]),
            green: hex_byte(bytes[3], bytes[4]),
            blue: hex_byte(bytes[5], bytes[6]),
        }
    }
}

const fn hex_byte(high: u8, low: u8) -> u8 {
    hex_digit(high) * 16 + hex_digit(low)
}

const fn hex_digit(character: u8) -> u8 {
    match character {
        b'0'..=b'9' => character - b'0',
        b'a'..=b'f' => character - b'a' + 10,
        b'A'..=b'F' => character - b'A' + 10,
        _ => panic!("a theme colour holds only hex digits"),
    }
}

/// How much of a style survives the terminal's capabilities.
///
/// Three states, never two. `TERM=dumb` and a redirected stream emit **no SGR at
/// all**, while `NO_COLOR` strips the colour and **keeps the attributes**. Both
/// were measured. A renderer that collapses them drops the bold from every styled
/// span of every `NO_COLOR` invocation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ColorRendering {
    /// Emit the text bare. No escape sequence of any kind.
    Suppressed,
    /// Emit attributes, drop every colour.
    AttributesOnly,
    /// Emit attributes and colour, downgraded to this system.
    Colored(ColorSystem),
}

/// Decide how much of a style the resolved terminal keeps.
///
/// ```
/// use _native::color::{rendering, ColorRendering};
/// use _native::terminal::{AmbientColorInputs, ColorSystem, resolve_color};
///
/// let piped = resolve_color(&AmbientColorInputs::default());
/// assert_eq!(rendering(&piped), ColorRendering::Suppressed);
///
/// let truecolor_terminal = resolve_color(&AmbientColorInputs {
///     colorterm: Some("truecolor"),
///     is_a_tty: true,
///     ..AmbientColorInputs::default()
/// });
/// assert_eq!(
///     rendering(&truecolor_terminal),
///     ColorRendering::Colored(ColorSystem::Truecolor)
/// );
///
/// let no_color = resolve_color(&AmbientColorInputs {
///     colorterm: Some("truecolor"),
///     no_color: Some("1"),
///     is_a_tty: true,
///     ..AmbientColorInputs::default()
/// });
/// assert_eq!(rendering(&no_color), ColorRendering::AttributesOnly);
/// ```
pub fn rendering(capabilities: &TerminalCapabilities) -> ColorRendering {
    match capabilities.color_system {
        None => ColorRendering::Suppressed,
        Some(_) if capabilities.no_color => ColorRendering::AttributesOnly,
        Some(system) => ColorRendering::Colored(system),
    }
}

/// A colour as a style names it: an authored RGB triple, or a palette index.
///
/// The distinction is observable and not a modelling nicety. A truecolor triple
/// downgrades with the terminal — the theme's `#878c92` becomes `37` on a
/// 16-colour terminal. A palette colour like Rich's `"green"` is *already* an
/// index, so it emits `32` at every tier and downgrades to nothing. Collapsing the
/// two makes the highlighter's colours drift as the terminal changes.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StyleColor {
    /// Authored as RGB. Downgraded per tier.
    Triplet(ColorTriplet),
    /// One of the sixteen standard colours, by index. Tier-invariant.
    Palette(u8),
}

impl StyleColor {
    /// The SGR parameters this colour contributes as a foreground.
    pub fn foreground(self, system: ColorSystem) -> String {
        match self {
            StyleColor::Triplet(triplet) => foreground_parameters(triplet, system),
            StyleColor::Palette(number) => standard_parameters(number, 30, 82),
        }
    }

    /// The SGR parameters this colour contributes as a background.
    pub fn background(self, system: ColorSystem) -> String {
        match self {
            StyleColor::Triplet(triplet) => background_parameters(triplet, system),
            StyleColor::Palette(number) => standard_parameters(number, 40, 92),
        }
    }
}

/// Rich splits the sixteen standard colours across two SGR ranges, so the bright
/// half is offset by 82 (or 92) rather than continuing from 30 (or 40).
fn standard_parameters(number: u8, standard_base: u16, bright_base: u16) -> String {
    let number = u16::from(number);
    let base = if number < 8 { standard_base } else { bright_base };
    format!("{}", base + number)
}

/// The SGR parameters that paint `triplet` as a foreground colour.
///
/// ```
/// use _native::color::{foreground_parameters, ColorTriplet};
/// use _native::terminal::ColorSystem;
///
/// let teal = ColorTriplet::from_hex("#5cc8a8");
/// assert_eq!(foreground_parameters(teal, ColorSystem::Truecolor), "38;2;92;200;168");
/// assert_eq!(foreground_parameters(teal, ColorSystem::EightBit), "38;5;79");
/// assert_eq!(foreground_parameters(teal, ColorSystem::Standard), "37");
/// ```
pub fn foreground_parameters(triplet: ColorTriplet, system: ColorSystem) -> String {
    parameters(triplet, system, 38, 30, 82)
}

/// The SGR parameters that paint `triplet` as a background colour.
///
/// ```
/// use _native::color::{background_parameters, ColorTriplet};
/// use _native::terminal::ColorSystem;
///
/// let amber = ColorTriplet::from_hex("#e6b450");
/// assert_eq!(background_parameters(amber, ColorSystem::Truecolor), "48;2;230;180;80");
/// assert_eq!(background_parameters(amber, ColorSystem::EightBit), "48;5;179");
/// ```
pub fn background_parameters(triplet: ColorTriplet, system: ColorSystem) -> String {
    parameters(triplet, system, 48, 40, 92)
}

/// Rich splits the sixteen standard colours across two SGR ranges rather than one
/// contiguous run, so the bright half is offset by 82 (or 92) instead of 30 (or 40).
fn parameters(
    triplet: ColorTriplet,
    system: ColorSystem,
    extended: u16,
    standard_base: u16,
    bright_base: u16,
) -> String {
    match system {
        ColorSystem::Truecolor => {
            format!(
                "{extended};2;{};{};{}",
                triplet.red, triplet.green, triplet.blue
            )
        }
        ColorSystem::EightBit => format!("{extended};5;{}", downgrade_to_eight_bit(triplet)),
        ColorSystem::Standard => {
            let number = u16::from(downgrade_to_standard(triplet));
            let base = if number < 8 { standard_base } else { bright_base };
            format!("{}", base + number)
        }
    }
}

/// Map a truecolor triple onto the 256-colour palette, exactly as Rich does.
///
/// ```
/// use _native::color::{downgrade_to_eight_bit, ColorTriplet};
/// // The theme's teal accent, and a grey that lands on the grayscale ramp.
/// assert_eq!(downgrade_to_eight_bit(ColorTriplet::from_hex("#5cc8a8")), 79);
/// assert_eq!(downgrade_to_eight_bit(ColorTriplet::from_hex("#c9ccd3")), 251);
/// ```
pub fn downgrade_to_eight_bit(triplet: ColorTriplet) -> u8 {
    let (lightness, saturation) = lightness_and_saturation(triplet);
    if saturation < 0.15 {
        let gray = round_ties_even(lightness * 25.0);
        return match gray {
            0 => 16,
            25 => 231,
            _ => (231 + gray) as u8,
        };
    }
    let level = |component: u8| -> i64 {
        let component = f64::from(component);
        round_ties_even(if component < 95.0 {
            component / 95.0
        } else {
            1.0 + (component - 95.0) / 40.0
        })
    };
    (16 + 36 * level(triplet.red) + 6 * level(triplet.green) + level(triplet.blue)) as u8
}

/// Map a truecolor triple onto the sixteen standard colours, exactly as Rich does.
///
/// ```
/// use _native::color::{downgrade_to_standard, ColorTriplet};
/// assert_eq!(downgrade_to_standard(ColorTriplet::from_hex("#5cc8a8")), 7);
/// assert_eq!(downgrade_to_standard(ColorTriplet::from_hex("#000000")), 0);
/// ```
pub fn downgrade_to_standard(triplet: ColorTriplet) -> u8 {
    STANDARD_PALETTE
        .iter()
        .enumerate()
        .min_by_key(|(_, candidate)| redmean_distance(triplet, **candidate))
        .map(|(number, _)| number as u8)
        .expect("the standard palette holds sixteen colours")
}

/// Rich's weighted redmean distance, in integer arithmetic.
///
/// The `/ 2` and the two `>> 8` are Python's `//` and `>>`, and they must stay
/// integral: over a stride-3 sweep of the cube an otherwise identical float port
/// disagrees 56 times, and when it disagrees it picks an entirely different colour
/// rather than an adjacent one.
///
/// Rich takes the square root of this sum before comparing. The root is dropped
/// here because it is strictly monotonic over the reachable range — the sums stay
/// under 2^20, where consecutive roots differ by about 5e-4 against a double's
/// 2e-13 of precision, so no two distinct sums can round to one root. The
/// 1,499-row oracle proves the argmin end to end regardless.
fn redmean_distance(color: ColorTriplet, candidate: ColorTriplet) -> i64 {
    let red_mean = (i64::from(color.red) + i64::from(candidate.red)) / 2;
    let red = i64::from(color.red) - i64::from(candidate.red);
    let green = i64::from(color.green) - i64::from(candidate.green);
    let blue = i64::from(color.blue) - i64::from(candidate.blue);
    (((512 + red_mean) * red * red) >> 8) + 4 * green * green + (((767 - red_mean) * blue * blue) >> 8)
}

/// Lightness and saturation, following `colorsys.rgb_to_hls`. Hue is never read.
///
/// The saturation denominator above mid-lightness is `2.0 - maximum - minimum`
/// rather than `2.0 - (maximum + minimum)`. CPython changed this in gh-106498 and
/// the two forms differ in the last bit, which is enough to cross the 0.15
/// saturation threshold and select the other branch.
fn lightness_and_saturation(triplet: ColorTriplet) -> (f64, f64) {
    let red = f64::from(triplet.red) / 255.0;
    let green = f64::from(triplet.green) / 255.0;
    let blue = f64::from(triplet.blue) / 255.0;
    let maximum = red.max(green).max(blue);
    let minimum = red.min(green).min(blue);
    let lightness = (maximum + minimum) / 2.0;
    if minimum == maximum {
        return (lightness, 0.0);
    }
    let range = maximum - minimum;
    let saturation = if lightness <= 0.5 {
        range / (maximum + minimum)
    } else {
        range / (2.0 - maximum - minimum)
    };
    (lightness, saturation)
}

/// Python's `round`, which breaks ties to even.
///
/// Rust's `f64::round` breaks them away from zero. The two disagree at channel
/// bytes 155 and 235 in the cube path, and wherever `maximum + minimum` is 51,
/// 255 or 459 in the grayscale path.
fn round_ties_even(value: f64) -> i64 {
    value.round_ties_even() as i64
}

const STANDARD_PALETTE: [ColorTriplet; 16] = [
    ColorTriplet { red: 0, green: 0, blue: 0 },
    ColorTriplet { red: 170, green: 0, blue: 0 },
    ColorTriplet { red: 0, green: 170, blue: 0 },
    ColorTriplet { red: 170, green: 85, blue: 0 },
    ColorTriplet { red: 0, green: 0, blue: 170 },
    ColorTriplet { red: 170, green: 0, blue: 170 },
    ColorTriplet { red: 0, green: 170, blue: 170 },
    ColorTriplet { red: 170, green: 170, blue: 170 },
    ColorTriplet { red: 85, green: 85, blue: 85 },
    ColorTriplet { red: 255, green: 85, blue: 85 },
    ColorTriplet { red: 85, green: 255, blue: 85 },
    ColorTriplet { red: 255, green: 255, blue: 85 },
    ColorTriplet { red: 85, green: 85, blue: 255 },
    ColorTriplet { red: 255, green: 85, blue: 255 },
    ColorTriplet { red: 85, green: 255, blue: 255 },
    ColorTriplet { red: 255, green: 255, blue: 255 },
];

#[cfg(test)]
mod downgrade_tests {
    use super::*;
    use std::path::PathBuf;

    /// The oracle is read from `session-core`'s desk rather than copied into this
    /// crate. A copy grades itself against a stale probe set and reports success
    /// while blind — the table grew from 1,459 rows to 1,499 the day it was
    /// written, and a copy taken before that would still be passing.
    fn oracle() -> serde_json::Value {
        let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("thoughts/2026-08-28-search-rust-rewrite/teammates/session-core")
            .join("colour-downgrade-oracle.json");
        let bytes = std::fs::read(&path)
            .unwrap_or_else(|error| panic!("colour oracle missing at {}: {error}", path.display()));
        serde_json::from_slice(&bytes).expect("the colour oracle is valid JSON")
    }

    fn rows() -> Vec<(ColorTriplet, u8, u8)> {
        let oracle = oracle();
        ["palette", "algorithm_critical"]
            .iter()
            .flat_map(|section| {
                oracle[section]
                    .as_array()
                    .unwrap_or_else(|| panic!("the colour oracle has a {section} section"))
                    .clone()
            })
            .map(|row| {
                let rgb = row["rgb"].as_array().expect("each row carries an rgb triple");
                let component = |index: usize| rgb[index].as_u64().expect("a channel byte") as u8;
                (
                    ColorTriplet {
                        red: component(0),
                        green: component(1),
                        blue: component(2),
                    },
                    row["eight_bit"]["number"].as_u64().expect("an 8-bit number") as u8,
                    row["standard"]["number"].as_u64().expect("a standard number") as u8,
                )
            })
            .collect()
    }

    #[test]
    fn every_oracle_row_downgrades_to_richs_answer() {
        let rows = rows();
        assert!(
            rows.len() >= 1_499,
            "Expected the full colour oracle, got {} rows. A shrunken table passes vacuously.",
            rows.len()
        );
        let mut eight_bit_mismatches = Vec::new();
        let mut standard_mismatches = Vec::new();
        for (triplet, expected_eight_bit, expected_standard) in &rows {
            let eight_bit = downgrade_to_eight_bit(*triplet);
            if eight_bit != *expected_eight_bit {
                eight_bit_mismatches.push((*triplet, *expected_eight_bit, eight_bit));
            }
            let standard = downgrade_to_standard(*triplet);
            if standard != *expected_standard {
                standard_mismatches.push((*triplet, *expected_standard, standard));
            }
        }
        assert!(
            eight_bit_mismatches.is_empty(),
            "EIGHT_BIT downgrade differs from Rich on {} of {} rows: {:?}",
            eight_bit_mismatches.len(),
            rows.len(),
            &eight_bit_mismatches[..eight_bit_mismatches.len().min(8)]
        );
        assert!(
            standard_mismatches.is_empty(),
            "STANDARD downgrade differs from Rich on {} of {} rows: {:?}",
            standard_mismatches.len(),
            rows.len(),
            &standard_mismatches[..standard_mismatches.len().min(8)]
        );
    }

    /// The gate must fail against the wrong port anyone would plausibly write.
    /// Both halves are checked separately, because a cube-only falsification goes
    /// green the moment someone repairs the cube path and leaves the grayscale
    /// path naive — which is exactly what a red gate invites.
    #[test]
    fn the_oracle_rejects_a_half_away_from_zero_port() {
        fn naive_eight_bit(triplet: ColorTriplet, naive_cube: bool, naive_gray: bool) -> u8 {
            let (lightness, saturation) = lightness_and_saturation(triplet);
            if saturation < 0.15 {
                let scaled = lightness * 25.0;
                let gray = if naive_gray {
                    scaled.round() as i64
                } else {
                    round_ties_even(scaled)
                };
                return match gray {
                    0 => 16,
                    25 => 231,
                    _ => (231 + gray) as u8,
                };
            }
            let level = |component: u8| -> i64 {
                let component = f64::from(component);
                let scaled = if component < 95.0 {
                    component / 95.0
                } else {
                    1.0 + (component - 95.0) / 40.0
                };
                if naive_cube {
                    scaled.round() as i64
                } else {
                    round_ties_even(scaled)
                }
            };
            (16 + 36 * level(triplet.red) + 6 * level(triplet.green) + level(triplet.blue)) as u8
        }

        let rows = rows();
        let caught = |naive_cube: bool, naive_gray: bool| {
            rows.iter()
                .filter(|(triplet, expected, _)| {
                    naive_eight_bit(*triplet, naive_cube, naive_gray) != *expected
                })
                .count()
        };

        assert!(
            caught(true, false) > 0,
            "The oracle no longer catches a naive cube path. The gate is blind."
        );
        assert!(
            caught(false, true) > 0,
            "The oracle no longer catches a naive grayscale path. That is the half-fix \
             blind spot: a port with the cube repaired would pass while still wrong."
        );
        assert_eq!(
            caught(false, false),
            0,
            "The control failed: ties-to-even must reproduce the oracle exactly. \
             A failing control means the algorithm is wrong, not the rounding."
        );
    }

    /// A float redmean picks an entirely different colour, not an adjacent one.
    #[test]
    fn the_standard_distance_must_stay_integral() {
        fn float_distance(color: ColorTriplet, candidate: ColorTriplet) -> f64 {
            let red_mean = (f64::from(color.red) + f64::from(candidate.red)) / 2.0;
            let red = f64::from(color.red) - f64::from(candidate.red);
            let green = f64::from(color.green) - f64::from(candidate.green);
            let blue = f64::from(color.blue) - f64::from(candidate.blue);
            ((512.0 + red_mean) * red * red) / 256.0
                + 4.0 * green * green
                + ((767.0 - red_mean) * blue * blue) / 256.0
        }
        let float_match = |triplet: ColorTriplet| -> u8 {
            let mut best = 0usize;
            let mut best_distance = f64::INFINITY;
            for (number, candidate) in STANDARD_PALETTE.iter().enumerate() {
                let distance = float_distance(triplet, *candidate);
                if distance < best_distance {
                    best_distance = distance;
                    best = number;
                }
            }
            best as u8
        };
        let green = ColorTriplet { red: 9, green: 129, blue: 69 };
        assert_eq!(downgrade_to_standard(green), 8);
        assert_ne!(
            float_match(green),
            downgrade_to_standard(green),
            "The float port must still diverge here, or this guard has stopped guarding."
        );
    }

    #[test]
    fn no_color_keeps_attributes_while_a_dumb_terminal_keeps_nothing() {
        use crate::terminal::{AmbientColorInputs, resolve_color};
        let no_color = resolve_color(&AmbientColorInputs {
            colorterm: Some("truecolor"),
            term: Some("xterm-256color"),
            no_color: Some("1"),
            is_a_tty: true,
            ..AmbientColorInputs::default()
        });
        assert_eq!(rendering(&no_color), ColorRendering::AttributesOnly);

        let dumb = resolve_color(&AmbientColorInputs {
            colorterm: Some("truecolor"),
            term: Some("dumb"),
            is_a_tty: true,
            ..AmbientColorInputs::default()
        });
        assert_eq!(rendering(&dumb), ColorRendering::Suppressed);
    }

    /// A palette colour is tier-invariant; a triple is not. **This is the whole
    /// reason the two arms exist**, and collapsing them is caught on 54 of the 135
    /// recorded stderr cases — but only in composition, so this states it locally.
    ///
    /// Rich's `"red"` is already an index, so `print_error` emits `31` on a
    /// truecolor terminal and on a 16-colour one alike. The theme's `#878c92` is
    /// authored as RGB, so `print_hint` emits a triple at truecolor and `37` at
    /// STANDARD. A port that resolves both the same way makes the highlighter's
    /// colours drift as the terminal changes.
    #[test]
    fn a_palette_colour_is_tier_invariant_and_a_triple_is_not() {
        let systems = [ColorSystem::Truecolor, ColorSystem::EightBit, ColorSystem::Standard];

        let red = StyleColor::Palette(1);
        let rendered: Vec<String> = systems.iter().map(|s| red.foreground(*s)).collect();
        assert_eq!(
            rendered,
            vec!["31".to_string(); 3],
            "A palette index must emit the same parameters at every depth."
        );

        let themed = StyleColor::Triplet(ColorTriplet::from_hex("#878c92"));
        let rendered: Vec<String> = systems.iter().map(|s| themed.foreground(*s)).collect();
        assert_eq!(rendered, ["38;2;135;140;146", "38;5;245", "37"]);
        assert_eq!(
            rendered.iter().collect::<std::collections::HashSet<_>>().len(),
            3,
            "A triple must resolve differently at each depth, or the two arms have \
             been collapsed and the downgrade is not reaching authored colours."
        );
    }

    #[test]
    fn standard_parameters_split_across_two_sgr_ranges() {
        let black = ColorTriplet { red: 0, green: 0, blue: 0 };
        let white = ColorTriplet { red: 255, green: 255, blue: 255 };
        assert_eq!(foreground_parameters(black, ColorSystem::Standard), "30");
        assert_eq!(background_parameters(black, ColorSystem::Standard), "40");
        assert_eq!(foreground_parameters(white, ColorSystem::Standard), "97");
        assert_eq!(background_parameters(white, ColorSystem::Standard), "107");
    }
}
