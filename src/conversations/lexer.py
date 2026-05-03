from __future__ import annotations

import re

from pygments.lexer import RegexLexer, bygroups
from pygments.token import Generic, Literal, Name, Punctuation, Text


class XmlmdLexer(RegexLexer):
    """Pygments lexer for the ccc xmlmd conversation format.

    Handles naive messages (user/assistant without tool blocks) wrapped in XML-like
    tags, with optional YAML frontmatter. Also tokenizes XML-like tags embedded
    inside message content.
    """

    name = "xmlmd"
    aliases = ["xmlmd", "xmd"]
    filenames = ["*.xmd", "*.xmlmd"]
    flags = re.MULTILINE

    tokens = {
        "root": [
            # Frontmatter block: only at absolute document start
            (r"\A---\n", Punctuation, "frontmatter"),
            # Inter-message separator: standalone --- line (not at \A)
            (r"^---\n", Punctuation),
            # Closing tag: </tagname>
            (r"(</)([\w][\w-]*)(>)", bygroups(Punctuation, Name.Tag, Punctuation)),
            # Opening tag: <tagname — push into tag_attrs to parse attributes
            (r"(<)([\w][\w-]*)", bygroups(Punctuation, Name.Tag), "tag_attrs"),
            # Literal < not starting a tag (e.g. comparison operators, loose markup)
            (r"<(?![\w/])", Text),
            # Markdown heading line (role headers like ## User and content headings)
            (r"^#{1,6} [^\n]+\n", Generic.Heading),
            # Newlines
            (r"\n", Text),
            # Any other text (non-tag, non-heading start)
            (r"[^<\n]+", Text),
        ],
        "frontmatter": [
            # Closing fence
            (r"^---\n", Punctuation, "#pop"),
            # key: value lines — 5 groups so the trailing \n is emitted
            (
                r"^([\w_-]+)(:)( *)([^\n]*)(\n)",
                bygroups(Name.Attribute, Punctuation, Text, Literal.String, Text),
            ),
            # Blank lines within frontmatter
            (r"\n", Text),
        ],
        "tag_attrs": [
            # Whitespace between attributes
            (r"\s+", Text),
            # attr="value" — quoted attribute value (value may contain < >)
            (
                r'([\w_-]+)(=)(")([^"]*?)(")',
                bygroups(Name.Attribute, Punctuation, Punctuation, Literal.String, Punctuation),
            ),
            # Bare attribute with no value (defensive, shouldn't occur in practice)
            (r"[\w_-]+", Name.Attribute),
            # Self-closing or normal end of tag
            (r"/>", Punctuation, "#pop"),
            (r">", Punctuation, "#pop"),
        ],
    }
