from __future__ import annotations

import html
from collections.abc import Iterable

_INNER_BLOCK_ENCODING = "html"


def render_inner_xml_block(
    tag: str,
    body: str,
    attributes: Iterable[tuple[str, str]] = (),
) -> str:
    """Render an inner XML block with reversible delimiter encoding.

    >>> render_inner_xml_block("subagent-task", "keep </subagent-task> literal")
    '<subagent-task encoding="html">\nkeep &lt;/subagent-task&gt; literal\n</subagent-task>'
    """
    block_attributes = list(attributes)
    if f"</{tag}>" in body:
        body = html.escape(body, quote=False)
        block_attributes.append(("encoding", _INNER_BLOCK_ENCODING))

    attribute_text = " ".join(
        f'{name}="{value}"' for name, value in block_attributes
    )
    opening_tag = f"<{tag} {attribute_text}>" if attribute_text else f"<{tag}>"
    return f"{opening_tag}\n{body}\n</{tag}>"


def decode_inner_xml_block_body(body: str, encoding: str | None) -> str:
    """Decode an inner XML block body produced by the shared renderer.

    >>> decode_inner_xml_block_body("keep &lt;/thinking&gt; literal", "html")
    'keep </thinking> literal'
    """
    if encoding is None:
        return body
    if encoding != _INNER_BLOCK_ENCODING:
        raise ValueError(f"Unsupported inner block encoding: {encoding!r}.")
    return html.unescape(body)
