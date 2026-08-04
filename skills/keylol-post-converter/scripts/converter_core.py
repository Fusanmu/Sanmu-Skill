#!/usr/bin/env python3
"""Convert Markdown/plain text to Keylol-flavoured Discuz BBCode."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse


@dataclass
class Heading:
    level: int
    text: str
    line: int
    page: int = 1


@dataclass
class WarningItem:
    code: str
    message: str
    line: int | None = None


HEADING_SIZES = {1: 6, 2: 5, 3: 4, 4: 3, 5: 2, 6: 2}
DEFAULT_POST_BACKGROUND = "bg4.png"
BODY_FONT = "微软雅黑"
BODY_SIZE = 4
FENCE_RE = re.compile(r"^ {0,3}(\x60{3,}|~{3,})(.*)$")
ATX_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
LIST_RE = re.compile(r"^(\s*)([-+*]|\d+[.)])\s+(.+)$")
TABLE_DIVIDER_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
HTML_RE = re.compile(r"</?[A-Za-z][^>]*>")
RAW_BBCODE_RE = re.compile(
    r"\[(?:/?(?:b|i|u|s|url|img|quote|code|list|table|tr|td|align|size|font|page|hr))(?:=[^\]]+)?\]",
    re.IGNORECASE,
)


def read_source(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeError("Input is not valid UTF-8, UTF-8 with BOM, or GB18030 text")


def strip_frontmatter(text: str) -> tuple[str, int]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text, 0
    for index in range(1, min(len(lines), 200)):
        if lines[index].strip() in {"---", "..."}:
            return "\n".join(lines[index + 1 :]), index + 1
    return text, 0


def plain_inline(text: str) -> str:
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\x60([^\x60]+)\x60", r"\1", text)
    text = re.sub(r"[*_~]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def is_remote_url(target: str) -> bool:
    parsed = urlparse(target.strip())
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def convert_inline(text: str, warnings: list[WarningItem], line: int) -> str:
    placeholders: dict[str, str] = {}

    def protect(value: str) -> str:
        token = f"\x00KLP{len(placeholders)}\x00"
        placeholders[token] = value
        return token

    def image_repl(match: re.Match[str]) -> str:
        alt, target = match.group(1), match.group(2).strip()
        if is_remote_url(target):
            return protect(f"[img]{target}[/img]")
        warnings.append(
            WarningItem(
                "local-image",
                f"Local or relative image requires manual upload: {target}",
                line,
            )
        )
        label = alt.strip() or target
        return protect(f"【待上传图片：{label}（{target}）】")

    def link_repl(match: re.Match[str]) -> str:
        label, target = match.group(1), match.group(2).strip()
        return protect(f"[url={target}]{label}[/url]")

    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", image_repl, text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link_repl, text)
    text = re.sub(
        r"\x60([^\x60\n]+)\x60",
        lambda m: protect(f"[font=Courier New]{m.group(1)}[/font]"),
        text,
    )
    text = re.sub(
        r"<((?:https?://|mailto:)[^>]+)>",
        lambda m: protect(f"[url]{m.group(1)}[/url]"),
        text,
    )
    text = re.sub(r"\*\*(.+?)\*\*", r"[b]\1[/b]", text)
    text = re.sub(r"__(.+?)__", r"[b]\1[/b]", text)
    text = re.sub(r"~~(.+?)~~", r"[s]\1[/s]", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"[i]\1[/i]", text)
    text = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", r"[i]\1[/i]", text)
    text = re.sub(r" {2,}$", "", text)

    for token, value in placeholders.items():
        text = text.replace(token, value)
    return text


def split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line)]


def table_to_bbcode(
    rows: list[tuple[int, str]], warnings: list[WarningItem]
) -> str:
    parsed = [split_table_row(row) for _, row in rows]
    width = max((len(row) for row in parsed), default=0)
    if any(len(row) != width for row in parsed):
        warnings.append(
            WarningItem(
                "irregular-table",
                "Table rows contain different numbers of cells; missing cells were padded.",
                rows[0][0] if rows else None,
            )
        )
    output = ["[table]"]
    for row_index, cells in enumerate(parsed):
        padded = cells + [""] * (width - len(cells))
        output.append("[tr]")
        for cell in padded:
            value = convert_inline(cell, warnings, rows[row_index][0])
            if row_index == 0:
                value = f"[b]{value}[/b]"
            output.append(f"[td]{value}[/td]")
        output.append("[/tr]")
    output.append("[/table]")
    return "\n".join(output)


def style_body(text: str, *, indent: bool = True) -> str:
    if indent:
        text = "　　" + text.lstrip(" \t　")
    return f"[font={BODY_FONT}][size={BODY_SIZE}]{text}[/size][/font]"


def heading_to_bbcode(
    level: int,
    text: str,
    warnings: list[WarningItem],
    line: int,
    split_level: int,
) -> str:
    converted = convert_inline(text, warnings, line)
    if split_level and level == split_level:
        return f"[K0]{converted}[/K0]"
    if split_level and level == split_level + 1:
        return f"[K1]{converted}[/K1]"
    size = HEADING_SIZES[level]
    result = f"[size={size}][b]{converted}[/b][/size]"
    return result


def convert_document(
    source: str,
    *,
    split_level: int = 2,
    include_toc: bool = True,
    toc_depth: int = 3,
    post_background: str | None = DEFAULT_POST_BACKGROUND,
) -> tuple[str, dict]:
    source, removed_frontmatter_lines = strip_frontmatter(source)
    lines = source.splitlines()
    warnings: list[WarningItem] = []
    headings: list[Heading] = []
    output: list[str] = []
    paragraph: list[tuple[int, str]] = []
    current_content_page = 1
    split_seen = False
    document_title: str | None = None

    def source_line(index: int) -> int:
        return index + 1 + removed_frontmatter_lines

    def flush_paragraph() -> None:
        if not paragraph:
            return
        converted = [
            convert_inline(value, warnings, number) for number, value in paragraph
        ]
        output.append("\n".join(style_body(value) for value in converted))
        paragraph.clear()

    index = 0
    while index < len(lines):
        line = lines[index]
        number = source_line(index)

        fence = FENCE_RE.match(line)
        if fence:
            flush_paragraph()
            marker = fence.group(1)
            code_lines: list[str] = []
            index += 1
            closed = False
            while index < len(lines):
                candidate = lines[index]
                if re.match(
                    rf"^ {{0,3}}{re.escape(marker[0])}{{{len(marker)},}}\s*$",
                    candidate,
                ):
                    closed = True
                    break
                code_lines.append(candidate)
                index += 1
            if not closed:
                warnings.append(
                    WarningItem(
                        "unclosed-code-fence",
                        "Code fence was closed at end of file.",
                        number,
                    )
                )
            output.append("[code]\n" + "\n".join(code_lines) + "\n[/code]")
            index += 1 if closed else 0
            continue

        heading_match = ATX_HEADING_RE.match(line)
        setext_level = 0
        setext_text = ""
        if (
            not heading_match
            and line.strip()
            and index + 1 < len(lines)
            and re.match(r"^ {0,3}(=+|-+)\s*$", lines[index + 1])
        ):
            setext_level = 1 if lines[index + 1].lstrip().startswith("=") else 2
            setext_text = line.strip()

        if heading_match or setext_level:
            flush_paragraph()
            if heading_match:
                level = len(heading_match.group(1))
                raw_text = heading_match.group(2)
                consumed = 1
            else:
                level = setext_level
                raw_text = setext_text
                consumed = 2

            if split_level and level == split_level:
                if split_seen:
                    output.append("[page]")
                    current_content_page += 1
                split_seen = True

            headings.append(
                Heading(level, plain_inline(raw_text), number, current_content_page)
            )
            if level == 1 and document_title is None:
                document_title = plain_inline(raw_text)
            else:
                output.append(
                    heading_to_bbcode(
                        level, raw_text, warnings, number, split_level
                    )
                )
            index += consumed
            continue

        if not line.strip():
            flush_paragraph()
            index += 1
            continue

        if (
            index + 1 < len(lines)
            and "|" in line
            and TABLE_DIVIDER_RE.match(lines[index + 1])
        ):
            flush_paragraph()
            rows: list[tuple[int, str]] = [(number, line)]
            index += 2
            while (
                index < len(lines) and "|" in lines[index] and lines[index].strip()
            ):
                rows.append((source_line(index), lines[index]))
                index += 1
            output.append(table_to_bbcode(rows, warnings))
            continue

        if re.match(r"^ {0,3}((\*\s*){3,}|(-\s*){3,}|(_\s*){3,})$", line):
            flush_paragraph()
            output.append("[hr]")
            index += 1
            continue

        if line.startswith("    "):
            flush_paragraph()
            code_lines = []
            while index < len(lines) and (
                lines[index].startswith("    ") or not lines[index].strip()
            ):
                code_lines.append(
                    lines[index][4:] if lines[index].startswith("    ") else ""
                )
                index += 1
            output.append("[code]\n" + "\n".join(code_lines).rstrip() + "\n[/code]")
            continue

        if re.match(r"^ {0,3}>", line):
            flush_paragraph()
            quote_lines: list[str] = []
            while index < len(lines) and re.match(r"^ {0,3}>", lines[index]):
                raw = re.sub(r"^ {0,3}> ?", "", lines[index])
                quote_lines.append(
                    convert_inline(raw, warnings, source_line(index))
                )
                index += 1
            output.append("[quote]\n" + "\n".join(quote_lines) + "\n[/quote]")
            continue

        list_match = LIST_RE.match(line)
        if list_match:
            flush_paragraph()
            ordered = bool(re.match(r"\d", list_match.group(2)))
            tag = "[list=1]" if ordered else "[list]"
            list_lines = [tag]
            while index < len(lines):
                item = LIST_RE.match(lines[index])
                if not item or bool(re.match(r"\d", item.group(2))) != ordered:
                    break
                if item.group(1):
                    warnings.append(
                        WarningItem(
                            "nested-list-flattened",
                            "Nested list indentation was flattened.",
                            source_line(index),
                        )
                    )
                value = item.group(3)
                task = re.match(r"^\[([ xX])\]\s+(.*)$", value)
                if task:
                    value = (
                        "☑ " if task.group(1).lower() == "x" else "☐ "
                    ) + task.group(2)
                list_lines.append(
                    "[*]"
                    + style_body(
                        convert_inline(value, warnings, source_line(index)),
                        indent=False,
                    )
                )
                index += 1
            list_lines.append("[/list]")
            output.append("\n".join(list_lines))
            continue

        if HTML_RE.search(line):
            warnings.append(
                WarningItem(
                    "raw-html",
                    "Raw HTML was preserved as text and may not render.",
                    number,
                )
            )
        if RAW_BBCODE_RE.search(line):
            warnings.append(
                WarningItem(
                    "raw-bbcode",
                    "Existing BBCode was preserved; check nested tags.",
                    number,
                )
            )
        paragraph.append((number, line))
        index += 1

    flush_paragraph()
    content = "\n\n".join(part for part in output if part != "").strip() + "\n"

    toc_headings = [
        heading for heading in headings if heading.level == split_level
    ]
    toc_added = include_toc and bool(toc_headings)
    if include_toc and not toc_headings:
        warnings.append(
            WarningItem("empty-toc", "No headings were found; the TOC was omitted.")
        )

    prefixes: list[str] = []
    if post_background:
        prefixes.append(f"[postbg]{post_background}[/postbg]")
    if toc_added:
        toc_lines = ["[index]"]
        for number, heading in enumerate(toc_headings, start=1):
            toc_lines.append(f"[#{number}]{heading.text}")
        toc_lines.append("[/index]")
        prefixes.append("\n".join(toc_lines))
    if prefixes:
        content = "\n".join(prefixes) + "\n\n" + content

    report = {
        "status": "ok",
        "layout": "keylol-native",
        "document_title": document_title,
        "page_count": current_content_page,
        "toc_included": toc_added,
        "index_included": toc_added,
        "post_background": post_background,
        "split_level": split_level,
        "toc_depth": toc_depth,
        "headings": [asdict(heading) for heading in headings],
        "warnings": [asdict(item) for item in warnings],
        "stats": {
            "source_lines": len(lines) + removed_frontmatter_lines,
            "heading_count": len(headings),
            "warning_count": len(warnings),
        },
    }
    return content, report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert Markdown/plain text to Keylol forum BBCode."
    )
    parser.add_argument(
        "input", nargs="?", type=Path, help="Input .md, .markdown, or .txt file"
    )
    parser.add_argument("-o", "--output", type=Path, help="Output BBCode text file")
    parser.add_argument("--report", type=Path, help="Optional JSON diagnostics report")
    parser.add_argument(
        "--split-level",
        type=int,
        default=2,
        choices=range(0, 7),
        metavar="0-6",
        help="Heading level that starts pages; 0 disables content pagination (default: 2)",
    )
    parser.add_argument(
        "--toc-depth",
        type=int,
        default=3,
        choices=range(1, 7),
        metavar="1-6",
        help="Compatibility option; native index uses page headings only",
    )
    toc_group = parser.add_mutually_exclusive_group()
    toc_group.add_argument(
        "--toc", dest="include_toc", action="store_true", default=True
    )
    toc_group.add_argument("--no-toc", dest="include_toc", action="store_false")
    background_group = parser.add_mutually_exclusive_group()
    background_group.add_argument(
        "--post-background",
        default=DEFAULT_POST_BACKGROUND,
        metavar="FILE",
        help="Keylol post background filename (default: bg4.png)",
    )
    background_group.add_argument(
        "--no-post-background",
        dest="post_background",
        action="store_const",
        const=None,
        help="Omit the [postbg] tag",
    )
    parser.add_argument(
        "--stdout", action="store_true", help="Write converted BBCode to stdout"
    )
    parser.add_argument(
        "--self-test", action="store_true", help="Run bundled conversion checks"
    )
    return parser


def run_self_test() -> int:
    sample = """---
title: Test
---
# 示例评测

前言含有 **重点**、[链接](https://example.com) 和 \x60code\x60。
资料见 https://example.com/path，严重剧透警告。

　　原文已经缩进的段落。

## 战斗系统

### 手感

- 快速
- 稳定

| 项目 | 结果 |
| --- | --- |
| 手感 | 优秀 |

\x60\x60\x60python
print("line 1")
print("line 2")
\x60\x60\x60

## 总结

![封面](images/cover.png)
"""
    converted, report = convert_document(sample)
    checks: Iterable[tuple[bool, str]] = (
        (converted.startswith("[postbg]bg4.png[/postbg]"), "post background"),
        (
            "[index]\n[#1]战斗系统\n[#2]总结\n[/index]" in converted,
            "native index",
        ),
        ("[K0]战斗系统[/K0]" in converted, "K0 heading"),
        ("[K1]手感[/K1]" in converted, "K1 heading"),
        ("[page]\n\n[K0]总结[/K0]" in converted, "page markers"),
        ("示例评测" not in converted, "document title omitted from body"),
        ("第2页" not in converted, "no simulated page numbers"),
        ("[font=微软雅黑][size=4]　　前言" in converted, "styled paragraph"),
        (
            "[/size][/font]\n[font=微软雅黑][size=4]　　资料见" in converted,
            "source-line paragraph indentation",
        ),
        (
            f"[font=微软雅黑][size=4]{'　' * 2}原文已经缩进的段落。[/size][/font]"
            in converted
            and f"[size=4]{'　' * 4}原文已经缩进的段落。" not in converted,
            "existing indentation normalized",
        ),
        ("[*][font=微软雅黑][size=4]快速[/size][/font]" in converted, "styled list"),
        ("[b]重点[/b]" in converted, "bold conversion"),
        (
            "[url]https://example.com/path[/url]，严重剧透警告" in converted,
            "bare URL punctuation boundary",
        ),
        ("[table]" in converted and "[td]" in converted, "table conversion"),
        (
            'print("line 1")\nprint("line 2")' in converted,
            "code newlines",
        ),
        (
            any(w["code"] == "local-image" for w in report["warnings"]),
            "local image warning",
        ),
        (report["page_count"] == 2, "page count"),
        (report["document_title"] == "示例评测", "document title report"),
    )
    failed = [name for ok, name in checks if not ok]
    if failed:
        print(json.dumps({"status": "failed", "checks": failed}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "ok", "checks": "all"}, ensure_ascii=False))
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.self_test:
        return run_self_test()
    if args.input is None:
        print("error: input is required unless --self-test is used", file=sys.stderr)
        return 2
    if not args.input.is_file():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2
    if args.input.suffix.lower() not in {".md", ".markdown", ".txt"}:
        print("error: input must be .md, .markdown, or .txt", file=sys.stderr)
        return 2

    try:
        source, encoding = read_source(args.input)
        converted, report = convert_document(
            source,
            split_level=args.split_level,
            include_toc=args.include_toc,
            toc_depth=args.toc_depth,
            post_background=args.post_background,
        )
    except (OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    output = args.output or args.input.with_name(args.input.stem + ".keylol.txt")
    if output.resolve() == args.input.resolve():
        print("error: refusing to overwrite the source file", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(converted, encoding="utf-8-sig", newline="\n")

    report.update(
        {
            "input": str(args.input.resolve()),
            "input_encoding": encoding,
            "output": str(output.resolve()),
        }
    )
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        report["report"] = str(args.report.resolve())
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.stdout:
        sys.stdout.write(converted)
    else:
        print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
