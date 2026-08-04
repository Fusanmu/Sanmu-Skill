#!/usr/bin/env python3
"""CLI entry point with conservative bare-URL conversion."""

from __future__ import annotations

import re

import converter_core as core


_base_convert_inline = core.convert_inline


def convert_inline_with_bare_urls(text, warnings, line):
    converted = _base_convert_inline(text, warnings, line)

    def replace(match):
        value = match.group(0)
        url = value.rstrip(".,;!?，。；！？")
        suffix = value[len(url) :]
        return f"[url]{url}[/url]{suffix}"

    return re.sub(
        r"(?<![=\]])https?://[^\s<\[\]，。；！？、）】》」』]+",
        replace,
        converted,
    )


core.convert_inline = convert_inline_with_bare_urls


if __name__ == "__main__":
    raise SystemExit(core.main())
