#!/usr/bin/env python3
"""Summarize edit decisions between an AI draft and a human revision."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？!?])|\n+")
HIGH_RISK_RE = re.compile(
    r"不是|并非|没有|而是|却是|更是|未必|不一定|看似|真正|更重要的是|"
    r"不再只|归根结底|这也正是|起到了应有的作用|成熟的类型框架|重要原因|"
    r"让我|使我|令我|我意识到|我才明白|我终于|我开始|我愿意|我印象最深|"
    r"继续想|反复想起|久久回味|保留.{0,12}空间"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare an AI draft with the user's human revision."
    )
    parser.add_argument("draft", help="UTF-8 AI draft")
    parser.add_argument("revision", help="UTF-8 human revision")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit JSON")
    parser.add_argument("--diff", action="store_true", help="append a unified line diff")
    return parser.parse_args()


def read(path_arg: str) -> str:
    path = Path(path_arg)
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"cannot read {path}: {exc}") from exc


def headings(text: str) -> list[dict[str, object]]:
    return [
        {"level": len(match.group(1)), "title": re.sub(r"[*_`]", "", match.group(2)).strip()}
        for match in HEADING_RE.finditer(text)
    ]


def prose_sentences(text: str) -> list[str]:
    text = HEADING_RE.sub("", text)
    result: list[str] = []
    for part in SENTENCE_SPLIT_RE.split(text):
        part = re.sub(r"\s+", " ", part).strip()
        if len(part) >= 8 and not re.match(r"^(?:[-*+] |\d+[.)])", part):
            result.append(part)
    return result


def normalize(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE)


def changed_headings(before: list[dict[str, object]], after: list[dict[str, object]]) -> list[dict[str, object]]:
    before_titles = [str(item["title"]) for item in before]
    after_titles = [str(item["title"]) for item in after]
    matcher = difflib.SequenceMatcher(a=before_titles, b=after_titles, autojunk=False)
    changes: list[dict[str, object]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changes.append({"kind": tag, "before": before[i1:i2], "after": after[j1:j2]})
    return changes


def removed_risky_sentences(before: list[str], after: list[str]) -> list[str]:
    after_norm = [normalize(value) for value in after]
    removed: list[str] = []
    for sentence in before:
        if not HIGH_RISK_RE.search(sentence):
            continue
        key = normalize(sentence)
        if not key:
            continue
        best = max((difflib.SequenceMatcher(a=key, b=value, autojunk=False).ratio() for value in after_norm), default=0.0)
        if best < 0.72:
            removed.append(sentence)
    return removed


def paragraph_count(text: str) -> int:
    blocks = re.split(r"\n\s*\n", text)
    return sum(bool(block.strip()) and not block.lstrip().startswith("#") for block in blocks)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parse_args()
    try:
        draft = read(args.draft)
        revision = read(args.revision)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    before_headings = headings(draft)
    after_headings = headings(revision)
    before_sentences = prose_sentences(draft)
    after_sentences = prose_sentences(revision)
    payload = {
        "files": {"draft": str(Path(args.draft)), "revision": str(Path(args.revision))},
        "summary": {
            "draft_characters": len(draft),
            "revision_characters": len(revision),
            "character_delta": len(revision) - len(draft),
            "draft_paragraphs": paragraph_count(draft),
            "revision_paragraphs": paragraph_count(revision),
            "draft_headings": len(before_headings),
            "revision_headings": len(after_headings),
        },
        "heading_changes": changed_headings(before_headings, after_headings),
        "removed_high_risk_sentences": removed_risky_sentences(before_sentences, after_sentences),
    }

    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        summary = payload["summary"]
        print("AI draft → human revision comparison")
        print(
            f"characters: {summary['draft_characters']} → {summary['revision_characters']} "
            f"({summary['character_delta']:+d})"
        )
        print(f"paragraphs: {summary['draft_paragraphs']} → {summary['revision_paragraphs']}")
        print(f"headings: {summary['draft_headings']} → {summary['revision_headings']}")
        print("\nHeading changes:")
        if payload["heading_changes"]:
            for change in payload["heading_changes"]:
                old = " | ".join(str(item["title"]) for item in change["before"]) or "∅"
                new = " | ".join(str(item["title"]) for item in change["after"]) or "∅"
                print(f"- {change['kind']}: {old} → {new}")
        else:
            print("- none")
        print("\nRemoved or substantially rewritten high-risk sentences:")
        risky = payload["removed_high_risk_sentences"]
        if risky:
            for sentence in risky:
                shortened = sentence if len(sentence) <= 160 else sentence[:159] + "…"
                print(f"- {shortened}")
        else:
            print("- none detected")

    if args.diff:
        print("\nUnified diff:")
        print(
            "".join(
                difflib.unified_diff(
                    draft.splitlines(keepends=True),
                    revision.splitlines(keepends=True),
                    fromfile=args.draft,
                    tofile=args.revision,
                )
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
