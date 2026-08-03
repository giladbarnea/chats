from __future__ import annotations

import html
import re
from collections.abc import Iterable

from .registry import ContentBlockType

_INNER_BLOCK_ENCODING = "html"
_INNER_BLOCK_TAG_PATTERN = "|".join(
    re.escape(block_type.value.xml_tag)
    for block_type in ContentBlockType
    if block_type.value.header is None
)
_INNER_XML_BLOCK_OPENING_PATTERN = re.compile(
    rf"^<(?:{_INNER_BLOCK_TAG_PATTERN})"
    r'(?:\s+[\w-]+="[^"]*")*>',
    re.MULTILINE,
)
INNER_XML_BLOCK_PATTERN = re.compile(
    rf"^<(?P<tag>{_INNER_BLOCK_TAG_PATTERN})"
    r'(?P<attrs>(?:\s+[\w-]+="[^"]*")*)>'
    r"(?P<body>.*?)</(?P=tag)>$",
    re.DOTALL | re.MULTILINE,
)


def encode_xml_text(text: str) -> tuple[str, str | None]:
    """Encode message text that would collide with a canonical inner block.

    >>> encode_xml_text("<thinking>literal</thinking>")
    ('&lt;thinking&gt;literal&lt;/thinking&gt;', 'html')
    >>> encode_xml_text("plain text")
    ('plain text', None)
    >>> encode_xml_text("literal\\n<thinking>\\nunclosed")[1]
    'html'
    """
    if _INNER_XML_BLOCK_OPENING_PATTERN.search(text) is None:
        return text, None
    return html.escape(text, quote=False), _INNER_BLOCK_ENCODING


def render_inner_xml_block(
    tag: str,
    body: str,
    attributes: Iterable[tuple[str, str]] = (),
    *,
    encode_transport: bool,
) -> str:
    """Render an inner XML block with optional reversible delimiter encoding.

    >>> render_inner_xml_block(
    ...     "subagent-task", "keep </subagent-task> literal", encode_transport=True
    ... )
    '<subagent-task encoding="html">\nkeep &lt;/subagent-task&gt; literal\n</subagent-task>'
    """
    block_attributes = list(attributes)
    if encode_transport and f"</{tag}>" in body:
        body = html.escape(body, quote=False)
        block_attributes.append(("encoding", _INNER_BLOCK_ENCODING))

    attribute_text = " ".join(
        f'{name}="{value}"' for name, value in block_attributes
    )
    opening_tag = f"<{tag} {attribute_text}>" if attribute_text else f"<{tag}>"
    return f"{opening_tag}\n{body}\n</{tag}>"


def decode_xml_transport_body(body: str, encoding: str | None) -> str:
    """Decode a body produced by the shared XML transport.

    >>> decode_xml_transport_body("keep &lt;/thinking&gt; literal", "html")
    'keep </thinking> literal'
    """
    if encoding is None:
        return body
    if encoding != _INNER_BLOCK_ENCODING:
        raise ValueError(f"Unsupported XML transport encoding: {encoding!r}.")
    return html.unescape(body)
