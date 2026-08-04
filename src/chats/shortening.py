from __future__ import annotations

from dataclasses import dataclass

DEFAULT_SHORT_MAX_CHARS = 500
MIN_SHORT_MAX_CHARS = 8
PROGRESSIVE_SHORT_COMPONENTS = frozenset({"p", "progressive"})


@dataclass(frozen=True)
class ShortPolicy:
    """A complete shortening limit and progression mode."""

    max_chars: int
    progressive: bool

    def effective_max_chars(
        self,
        position: int | None,
        qualifying_count: int,
    ) -> int:
        """Return this policy's limit at one progressive sequence position.

        >>> ShortPolicy(128, True).effective_max_chars(1, 4)
        48
        """
        if not self.progressive or position is None or qualifying_count <= 1:
            return self.max_chars
        return MIN_SHORT_MAX_CHARS + (
            position * (self.max_chars - MIN_SHORT_MAX_CHARS)
            // (qualifying_count - 1)
        )


@dataclass(frozen=True)
class ShortSpec:
    """A parsed short spec whose omitted fields can inherit a policy."""

    max_chars: int | None
    progressive: bool

    def resolve(self, default: ShortPolicy) -> ShortPolicy:
        """Fill this spec's omitted limit from the supplied policy."""
        return ShortPolicy(
            max_chars=self.max_chars or default.max_chars,
            progressive=self.progressive,
        )


DEFAULT_SHORT_POLICY = ShortPolicy(DEFAULT_SHORT_MAX_CHARS, False)


def parse_short_spec(candidate: str) -> ShortSpec:
    """Parse the shared global and tool-local short-spec grammar.

    >>> parse_short_spec("progressive=32")
    ShortSpec(max_chars=32, progressive=True)
    """
    progressive_component, separator, maximum_component = candidate.partition("=")
    is_progressive = (
        progressive_component.lower() in PROGRESSIVE_SHORT_COMPONENTS
    )
    progressive_with_limit = is_progressive and bool(separator)

    if progressive_with_limit and not maximum_component.isdigit():
        raise _invalid_short_spec(candidate)
    if progressive_with_limit and int(maximum_component) < MIN_SHORT_MAX_CHARS:
        raise _invalid_short_spec(candidate)
    if progressive_with_limit:
        return ShortSpec(max_chars=int(maximum_component), progressive=True)

    if is_progressive:
        return ShortSpec(max_chars=None, progressive=True)
    if separator or not candidate.isdigit():
        raise _invalid_short_spec(candidate)

    maximum = int(candidate)
    if maximum < MIN_SHORT_MAX_CHARS:
        raise _invalid_short_spec(candidate)
    return ShortSpec(max_chars=maximum, progressive=False)


def looks_like_short_spec(candidate: str) -> bool:
    """Return whether a detached token should stay attached to `--short`."""
    components = candidate.split(":")
    incomplete_numeric_spec = (
        len(components) == 2
        and components[0].isdigit()
        and int(components[0]) >= MIN_SHORT_MAX_CHARS
        and not components[1]
    )
    progressive_component = candidate.partition("=")[0]
    return not candidate or incomplete_numeric_spec or any(
        component.lower() in PROGRESSIVE_SHORT_COMPONENTS
        for component in components
    ) or progressive_component.lower() in PROGRESSIVE_SHORT_COMPONENTS


def _invalid_short_spec(candidate: str) -> ValueError:
    return ValueError(
        f"Invalid short value: {candidate!r}. Expected N, p, progressive, "
        "p=N, or progressive=N with N >= 8."
    )
