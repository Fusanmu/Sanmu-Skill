#!/usr/bin/env python3
"""Flag common fidelity and template-style risks in a Chinese game-review draft."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


STYLE_RULES = (
    ("binary_contrast", re.compile(r"(?:并)?不是[^。！？\n]{0,100}(?:而是|却是)"), 1,
     "重复的“不是……而是……”容易形成统一的洞见腔。"),
    ("not_only_but", re.compile(r"(?:这)?不(?:只|仅)是[^。！？\n]{0,100}(?:更是|也是)"), 0,
     "“不只是……更是……”通常在替普通判断拔高。"),
    ("truly", re.compile(r"真正"), 1,
     "“真正”重复出现时容易把判断统一成评论家口吻。"),
    ("importance_cue", re.compile(r"更重要的是|归根结底|这说明(?:了)?"), 1,
     "显式意义提示重复时，往往可以直接删去或改成普通陈述。"),
)

PSYCHOLOGY_RULE = re.compile(
    r"让我|使我|令我|推动我|促使我|我愿意|我意识到|我终于|我开始|我突然|我才明白"
)

SUMMARY_OPENING = re.compile(
    r"^(?:因此|所以|总之|总的来说|归根结底|最终|这也是|这使得|由此看来)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("draft", help="Markdown draft path, or - for UTF-8 stdin")
    parser.add_argument(
        "--anchor", action="append", default=[], help="Expected voice anchor; repeat as needed"
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when warnings exist")
    return parser.parse_args()


def read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text(encoding="utf-8-sig")


def line_number(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def body_without_headings(text: str) -> str:
    lines = []
    fenced = False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            lines.append("\n")
        elif fenced or line.lstrip().startswith("#"):
            lines.append("\n")
        else:
            lines.append(line)
    return "".join(lines)


def add_match_warnings(warnings: list[dict], text: str, rule: str, matches, message: str) -> None:
    for match in matches:
        warnings.append(
            {
                "severity": "warning",
                "rule": rule,
                "line": line_number(text, match.start()),
                "excerpt": match.group(0).strip(),
                "message": message,
            }
        )


def section_endings(text: str) -> list[tuple[int, int, str]]:
    endings: list[tuple[int, int, str]] = []
    heading_line: int | None = None
    last_line: int | None = None
    last_text = ""
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            if heading_line is not None and last_line is not None:
                endings.append((heading_line, last_line, last_text))
            heading_line = number
            last_line = None
            last_text = ""
        elif heading_line is not None and line.strip() and not line.startswith("#"):
            last_line = number
            last_text = line.strip()
    if heading_line is not None and last_line is not None:
        endings.append((heading_line, last_line, last_text))
    return endings


def inspect(text: str, anchors: list[str]) -> list[dict]:
    warnings: list[dict] = []
    body = body_without_headings(text)

    for rule, pattern, allowed, message in STYLE_RULES:
        matches = list(pattern.finditer(body))
        if len(matches) > allowed:
            add_match_warnings(warnings, body, rule, matches[allowed:], message)

    add_match_warnings(
        warnings,
        body,
        "first_person_psychology",
        list(PSYCHOLOGY_RULE.finditer(body)),
        "回查观点账本：这处第一人称心理或因果必须来自用户原话或明确确认。",
    )

    endings = section_endings(text)
    summary_runs: list[list[tuple[int, int, str]]] = []
    current_run: list[tuple[int, int, str]] = []
    for ending in endings:
        if SUMMARY_OPENING.match(ending[2]):
            current_run.append(ending)
        else:
            if len(current_run) >= 3:
                summary_runs.append(current_run)
            current_run = []
    if len(current_run) >= 3:
        summary_runs.append(current_run)

    for run in summary_runs:
        for _heading_line, ending_line, ending in run:
            warnings.append(
                {
                    "severity": "notice",
                    "rule": "uniform_section_summary",
                    "line": ending_line,
                    "excerpt": ending[:120],
                    "message": "多个章节都以抽象总结收尾；考虑让部分章节停在例子、影响或保留意见上。",
                }
            )

    if not anchors:
        warnings.append(
            {
                "severity": "notice",
                "rule": "anchors_not_supplied",
                "line": None,
                "excerpt": "",
                "message": "未向检查器提供声音锚点；请人工确认核心章节保留了用户的判断方式。",
            }
        )
    else:
        for anchor in anchors:
            if anchor not in text:
                warnings.append(
                    {
                        "severity": "warning",
                        "rule": "missing_anchor",
                        "line": None,
                        "excerpt": anchor,
                        "message": "预期的声音锚点未出现在稿件中；确认是有意改写还是被媒体化语言抹平。",
                    }
                )
    return warnings


def main() -> int:
    args = parse_args()
    try:
        text = read_text(args.draft)
    except (OSError, UnicodeError) as exc:
        print(f"读取稿件失败：{exc}", file=sys.stderr)
        return 2

    warnings = inspect(text, args.anchor)
    payload = {"warning_count": len(warnings), "warnings": warnings}
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif not warnings:
        print("未发现机械检查警告；仍需完成人工保真回读。")
    else:
        print(f"发现 {len(warnings)} 项待复核内容：")
        for warning in warnings:
            where = f"第 {warning['line']} 行" if warning["line"] else "全文"
            excerpt = f"｜{warning['excerpt']}" if warning["excerpt"] else ""
            print(f"- [{warning['severity']}] {where}｜{warning['rule']}{excerpt}")
            print(f"  {warning['message']}")
    return 1 if args.strict and warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
