#!/usr/bin/env python3
"""Mechanical preflight checks for a Chinese personal game review.

The checker finds high-risk patterns; it never rewrites prose and cannot prove
that a draft is truthful or well written.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class Finding:
    severity: str
    code: str
    line: int | None
    message: str
    excerpt: str = ""


CONTRAST_RE = re.compile(
    r"(?:不是|并非|没有|不只是|不单是|不止是|并不只是)"
    r"[^。！？!?\n]{0,60}(?:而是|却是|反而是|更是)"
)
SOFT_CONTRAST_RE = re.compile(
    r"(?:未必|不一定|看似)[^。！？!?\n]{0,60}(?:却|但|其实|实际(?:上)?)"
)
REDUCTIVE_INSIGHT_RE = re.compile(
    r"(?:不再|不只|并非只)[^。！？!?\n]{0,12}(?:只是|只剩|依靠|靠|依赖)"
)
RISKY_FIRST_PERSON_RE = re.compile(
    r"让我|使我|令我|推动我|我意识到|我才明白|我终于|我开始|我愿意|我印象最深|"
    r"我(?:还|仍)(?:会)?继续想|通关后[^。！？!?\n]{0,12}(?:继续想|反复想起|回味)"
)
SOFT_CAUSAL_RE = re.compile(
    r"(?:撑起|撑住)[^。！？!?\n]{0,30}(?:流程|体验|游玩|战斗)|"
    r"(?:演出|美术|战斗|剧情|玩法)[^。！？!?\n]{0,16}(?:起了|发挥了)[^。！？!?\n]{0,8}作用|"
    r"(?:把|将)[^。！？!?\n]{0,16}(?:评价|分数)[^。！？!?\n]{0,10}(?:拉高|推高|往上推)|"
    r"比[^。！？!?\n]{1,30}更容易(?:让人)?(?:记住|留下印象)|"
    r"(?:也是|是)[^。！？!?\n]{0,20}(?:我)?(?:愿意)?(?:给出?|打出)"
    r"[^。！？!?\n]{0,8}(?:\d+|[六七八九十])分[^。！？!?\n]{0,10}(?:重要|主要|关键)原因"
)
GENERIC_REVIEW_PATTERNS = {
    "起到了应有的作用": re.compile(r"起到(?:了)?应有的作用"),
    "成熟的类型框架": re.compile(r"成熟的(?:类型|玩法|叙事)框架"),
    "作品自己的味道": re.compile(r"(?:作品|游戏)(?:自己|本身)的味道|保留了自己的味道"),
    "功能完整，衔接也顺": re.compile(r"功能(?:很)?完整[^。！？!?\n]{0,10}衔接(?:也|很)?顺"),
    "站到同类顶点": re.compile(r"站到(?:了)?同类(?:作品)?(?:的)?(?:顶点|顶尖)"),
    "这个分数给得很干脆": re.compile(r"(?:这个|这次)?(?:\d+|[六七八九十])分我给得(?:很)?(?:干脆|直接)"),
}
DEFENSIVE_EDITOR_PATTERNS = {
    "用正文解释例子的适用范围": re.compile(
        r"(?:这个|该)?例子只对应|只对应这(?:一|个)|没必要据此概括"
    ),
    "用正文汇报写作取舍": re.compile(
        r"(?:我)?不打算把[^。！？!?\n]{0,30}写成[^。！？!?\n]{0,20}(?:优点|缺点|重点)|"
        r"没有需要单独提醒(?:的)?(?:问题|地方)?"
    ),
}
SCOPE_AND_WORDING_PATTERNS = {
    "局部例子可能被扩大": re.compile(
        r"(?:Boss|BOSS|敌人|关卡|战斗|系统)[^。！？!?\n]{0,20}"
        r"(?:不只|并非只|不再只)(?:靠|依赖|剩)"
    ),
    "可能替缺少便利补写收益": re.compile(
        r"(?:也|反而)?(?:保留|留出|给了)[^。！？!?\n]{0,16}"
        r"(?:寻找|探索|发挥|选择|思考|试错)(?:的)?空间"
    ),
    "地图或物品语境中的可疑错词“标点”": re.compile(
        r"(?:地图|物品|收集物|坐标)[^。！？!?\n]{0,20}标点|"
        r"标点[^。！？!?\n]{0,20}(?:地图|物品|收集物|坐标)"
    ),
}
INSIGHT_PATTERNS = {
    "真正": re.compile(r"真正"),
    "更重要的是": re.compile(r"更重要的是"),
    "归根结底": re.compile(r"归根结底"),
    "这也正是": re.compile(r"这也正是"),
    "某种意义上": re.compile(r"(?:从)?某种意义上"),
    "值得一提的是": re.compile(r"值得一提的是"),
    "毫不夸张地说": re.compile(r"毫不夸张地说"),
}
ABSTRACT_TITLE_RE = re.compile(
    r"回响|回声|底色|温度|重量|答案|灵魂|旅程|情书|余韵|救赎|觉醒|撕裂|执念"
)
SLOGAN_TITLE_RE = re.compile(r"不是|而是|没有|真正|[！？?!]|——")
COMPRESSED_HEADING_RE = re.compile(
    r"先立住|压在(?:长战|流程|后期)|后期(?:开始)?发力|撑起(?:战斗|流程)|稳稳站住"
)
MOJIBAKE_RE = re.compile(r"锟斤拷|烫烫烫|屯屯屯|ï¿½|ã€|â€”|â€œ|â€")
ABSTRACT_END_RE = re.compile(
    r"这(?:也)?(?:正是|就是)|归根结底|从某种意义上|总而言之|总的来说|"
    r"这(?:足以|说明|意味着)|而这"
)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+] |\d+[.)]\s)")
FUNCTIONAL_HEADING_LABELS = {
    "前言",
    "缺点",
    "购买推荐",
    "购买建议",
    "结语",
    "总结",
    "评分",
    "个人评分",
    "推荐",
    "剧透说明",
}
STAGE_HEADING_RE = re.compile(
    r"^(?:初入|初到|初见|开局|前期|深入|逐步|一路|随后|中期|后期|最终|尾声|通关后)\s*[：:]"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check a Chinese game-review draft for fidelity and AI-pattern risks."
    )
    parser.add_argument("path", nargs="?", default="-", help="UTF-8 Markdown/text file, or - for stdin")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit JSON")
    return parser.parse_args()


def read_text(path_arg: str) -> tuple[str, str]:
    if path_arg == "-":
        return sys.stdin.read(), "<stdin>"
    path = Path(path_arg)
    try:
        return path.read_text(encoding="utf-8-sig"), str(path)
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"cannot read {path}: {exc}") from exc


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def clean_excerpt(value: str, limit: int = 100) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= limit else value[: limit - 1] + "…"


def is_functional_heading(title: str) -> bool:
    """Return whether a heading labels an article function rather than a review topic."""
    normalized = re.sub(r"[*_`]+", "", title).strip()
    if normalized in FUNCTIONAL_HEADING_LABELS:
        return True
    prefix = re.split(r"[：:]", normalized, maxsplit=1)[0].strip()
    return prefix in FUNCTIONAL_HEADING_LABELS


def first_h2_range(lines: list[str]) -> tuple[int, int] | None:
    starts = [i for i, line in enumerate(lines) if re.match(r"^##\s+", line)]
    if not starts:
        return None
    start = starts[0]
    end = starts[1] if len(starts) > 1 else len(lines)
    return start, end


def prose_paragraphs(lines: list[str]) -> list[tuple[int, str]]:
    paragraphs: list[tuple[int, str]] = []
    buffer: list[str] = []
    start_line = 0
    in_fence = False

    def flush() -> None:
        nonlocal buffer
        if buffer:
            text = " ".join(part.strip() for part in buffer).strip()
            if text:
                paragraphs.append((start_line, text))
            buffer = []

    for idx, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            flush()
            in_fence = not in_fence
            continue
        if in_fence or not stripped:
            flush()
            continue
        if HEADING_RE.match(stripped) or LIST_RE.match(stripped) or stripped.startswith((">", "|", "---")):
            flush()
            continue
        if not buffer:
            start_line = idx
        buffer.append(stripped)
    flush()
    return paragraphs


def visible_length(text: str) -> int:
    text = re.sub(r"!?\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"[`*_~#]", "", text)
    return len(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text))


def coefficient_of_variation(values: Iterable[int]) -> float:
    values = list(values)
    if len(values) < 2:
        return math.inf
    mean = statistics.mean(values)
    return statistics.pstdev(values) / mean if mean else math.inf


def section_endings(lines: list[str]) -> list[tuple[str, int, str]]:
    sections: list[tuple[str, int, str]] = []
    current_title: str | None = None
    current_line = 0
    body: list[tuple[int, str]] = []

    def flush() -> None:
        nonlocal body
        if current_title and body:
            joined = " ".join(value for _, value in body)
            sentences = [s.strip() for s in re.split(r"(?<=[。！？!?])", joined) if s.strip()]
            ending = sentences[-1] if sentences else joined
            sections.append((current_title, body[-1][0], clean_excerpt(ending, 80)))
        body = []

    for idx, raw in enumerate(lines, start=1):
        h2 = re.match(r"^##\s+(.+?)\s*$", raw)
        if h2:
            flush()
            current_title = h2.group(1)
            current_line = idx
            continue
        stripped = raw.strip()
        if current_title and stripped and not stripped.startswith(("#", "- ", "* ", ">", "|", "---", "```")):
            body.append((idx, stripped))
    flush()
    return sections


def section_paragraph_counts(lines: list[str]) -> list[tuple[str, int]]:
    starts: list[tuple[int, str]] = []
    for idx, raw in enumerate(lines):
        match = re.match(r"^##\s+(.+?)\s*$", raw)
        if match:
            starts.append((idx, match.group(1)))

    result: list[tuple[str, int]] = []
    for pos, (start, title) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        segment = lines[start + 1 : end]
        count = sum(visible_length(value) >= 20 for _, value in prose_paragraphs(segment))
        if count:
            result.append((title, count))
    return result


def run_checks(text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()

    if "\ufffd" in text:
        for idx, line in enumerate(lines, start=1):
            if "\ufffd" in line:
                findings.append(Finding("error", "UNICODE_REPLACEMENT", idx, "发现 Unicode 替换字符，文本可能已损坏。", clean_excerpt(line)))

    for idx, char in enumerate(text):
        code = ord(char)
        if (code < 32 and char not in "\n\r\t") or 0x7F <= code <= 0x9F:
            findings.append(Finding("error", "CONTROL_CHARACTER", line_number(text, idx), f"发现异常控制字符 U+{code:04X}。"))

    for match in MOJIBAKE_RE.finditer(text):
        findings.append(Finding("error", "MOJIBAKE", line_number(text, match.start()), "发现常见乱码片段。", clean_excerpt(match.group())))

    for match in CONTRAST_RE.finditer(text):
        findings.append(Finding("error", "BINARY_CONTRAST", line_number(text, match.start()), "发现二元洞见骨架，请改成直接陈述、条件、让步或具体影响。", clean_excerpt(match.group())))

    for match in SOFT_CONTRAST_RE.finditer(text):
        findings.append(Finding("warning", "SYNONYM_CONTRAST", line_number(text, match.start()), "发现同义二元结构，检查是否只替换了连接词而没有改变论证方式。", clean_excerpt(match.group())))

    for match in REDUCTIVE_INSIGHT_RE.finditer(text):
        findings.append(Finding("warning", "REDUCTIVE_INSIGHT", line_number(text, match.start()), "发现“不再只是／不再只剩／不只靠”式洞见，检查是否压低一端后自行扩大结论。", clean_excerpt(match.group())))

    lead_range = first_h2_range(lines)
    for label, pattern in INSIGHT_PATTERNS.items():
        matches = list(pattern.finditer(text))
        for match in matches:
            line = line_number(text, match.start())
            severity = "warning"
            code = "INSIGHT_TEMPLATE"
            if label == "真正" and lead_range and lead_range[0] + 1 <= line <= lead_range[1]:
                severity = "error"
                code = "LEAD_INSIGHT_TEMPLATE"
            findings.append(Finding(severity, code, line, f"发现高风险洞见套话“{label}”，检查是否可以直接说具体内容。", label))
        if len(matches) >= 2:
            findings.append(Finding("warning", "REPEATED_TEMPLATE", None, f"“{label}”出现 {len(matches)} 次，文章骨架可能重复。", label))

    for match in RISKY_FIRST_PERSON_RE.finditer(text):
        line = line_number(text, match.start())
        line_text = lines[line - 1] if 0 < line <= len(lines) else match.group()
        findings.append(Finding("warning", "FIRST_PERSON_CAUSALITY", line, "第一人称心理或因果必须回指已确认材料。", clean_excerpt(line_text)))

    for match in SOFT_CAUSAL_RE.finditer(text):
        line = line_number(text, match.start())
        line_text = lines[line - 1] if 0 < line <= len(lines) else match.group()
        findings.append(Finding("warning", "SOFT_CAUSAL_CLAIM", line, "抽象作用或评分因果必须回指已确认材料，不能由若干单项评价自动拼出。", clean_excerpt(line_text)))

    for label, pattern in GENERIC_REVIEW_PATTERNS.items():
        for match in pattern.finditer(text):
            line = line_number(text, match.start())
            line_text = lines[line - 1] if 0 < line <= len(lines) else match.group()
            findings.append(Finding("warning", "GENERIC_REVIEW_PHRASE", line, f"发现空泛的标准评测句“{label}”，请改成具体材料或删除。", clean_excerpt(line_text)))

    defensive_lines: set[int] = set()
    for label, pattern in DEFENSIVE_EDITOR_PATTERNS.items():
        for match in pattern.finditer(text):
            line = line_number(text, match.start())
            if line in defensive_lines:
                continue
            defensive_lines.add(line)
            line_text = lines[line - 1] if 0 < line <= len(lines) else match.group()
            findings.append(Finding("warning", "DEFENSIVE_EDITOR_NOTE", line, f"{label}。请把范围或取舍落实到主语和选材，不要把编辑规则写进正文。", clean_excerpt(line_text)))

    for label, pattern in SCOPE_AND_WORDING_PATTERNS.items():
        for match in pattern.finditer(text):
            line = line_number(text, match.start())
            line_text = lines[line - 1] if 0 < line <= len(lines) else match.group()
            findings.append(Finding("warning", "SCOPE_OR_WORDING_RISK", line, f"{label}，请按材料范围和句子实际词义复核。", clean_excerpt(line_text)))

    headings: list[tuple[int, int, str]] = []
    for idx, raw in enumerate(lines, start=1):
        match = HEADING_RE.match(raw)
        if not match:
            continue
        level = len(match.group(1))
        title = re.sub(r"[*_`]+", "", match.group(2)).strip()
        headings.append((level, idx, title))
        if ABSTRACT_TITLE_RE.search(title):
            findings.append(Finding("warning", "ABSTRACT_HEADING", idx, "标题含容易口号化的抽象词，请确认正文足以兑现。", title))
        if SLOGAN_TITLE_RE.search(title):
            findings.append(Finding("warning", "SLOGAN_HEADING", idx, "标题可能依赖反转、口号或强行修辞。", title))
        if COMPRESSED_HEADING_RE.search(title):
            findings.append(Finding("warning", "COMPRESSED_HEADING", idx, "标题含为了简短而压缩出的不自然搭配，请按普通中文朗读后重写。", title))

    h2_titles = [title for level, _, title in headings if level == 2 and not is_functional_heading(title)]
    if len(h2_titles) >= 4:
        de_pattern = [bool(re.match(r"^.{2,12}的.{2,12}$", title)) for title in h2_titles]
        if sum(de_pattern) / len(de_pattern) >= 0.8:
            findings.append(Finding("warning", "UNIFORM_HEADINGS", None, "多数小标题使用相同的“……的……”结构，检查是否为整齐而整齐。", " | ".join(h2_titles)))
        longest_stage_run = 0
        current_stage_run = 0
        for title in h2_titles:
            if STAGE_HEADING_RE.search(title):
                current_stage_run += 1
                longest_stage_run = max(longest_stage_run, current_stage_run)
            else:
                current_stage_run = 0
        if longest_stage_run >= 3:
            findings.append(Finding("warning", "UNIFORM_STAGE_HEADINGS", None, "连续使用阶段词生成小标题，检查是否把时间顺序误写成“初入／深入／后期：判断”模板。", " | ".join(h2_titles)))

    section_counts = [item for item in section_paragraph_counts(lines) if not is_functional_heading(item[0])]
    if len(section_counts) >= 4:
        frequencies: dict[int, int] = {}
        for _, count in section_counts:
            frequencies[count] = frequencies.get(count, 0) + 1
        common_count, common_frequency = max(frequencies.items(), key=lambda item: item[1])
        if common_frequency / len(section_counts) >= 0.75:
            excerpt = " | ".join(f"{title}={count}段" for title, count in section_counts)
            findings.append(Finding("warning", "UNIFORM_SECTION_PARAGRAPHS", None, f"多数章节都采用 {common_count} 段，检查是否重复同一种展开运动。", excerpt))

    paragraphs = [(line, value) for line, value in prose_paragraphs(lines) if visible_length(value) >= 40]
    lengths = [visible_length(value) for _, value in paragraphs]
    if len(lengths) >= 6 and coefficient_of_variation(lengths) < 0.18:
        findings.append(Finding("warning", "UNIFORM_PARAGRAPHS", None, "正文段落长度过分接近，检查是否每段都按同一模板展开。", f"段落长度：{lengths}"))

    endings = section_endings(lines)
    abstract_endings = [(title, line, ending) for title, line, ending in endings if ABSTRACT_END_RE.search(ending)]
    if len(abstract_endings) >= 2:
        excerpt = " | ".join(f"{title}: {ending}" for title, _, ending in abstract_endings[:4])
        findings.append(Finding("warning", "ABSTRACT_SECTION_ENDINGS", abstract_endings[0][1], "多节以抽象意义句收尾，请让部分章节停在例子、影响或普通判断上。", excerpt))

    return findings


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
        sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    args = parse_args()
    try:
        text, source = read_text(args.path)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    findings = run_checks(text)
    errors = sum(item.severity == "error" for item in findings)
    warnings = sum(item.severity == "warning" for item in findings)
    if args.as_json:
        payload = {
            "source": source,
            "summary": {"errors": errors, "warnings": warnings, "passed_hard_checks": errors == 0},
            "findings": [asdict(item) for item in findings],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"personal-game-review-prose: {errors} error(s), {warnings} warning(s) — {source}")
        if not findings:
            print("未发现机械规则能够识别的风险；仍需人工完成保真与文笔复核。")
        for item in findings:
            location = f"L{item.line}" if item.line else "GLOBAL"
            print(f"[{item.severity.upper()}] {item.code} {location}: {item.message}")
            if item.excerpt:
                print(f"  {item.excerpt}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
