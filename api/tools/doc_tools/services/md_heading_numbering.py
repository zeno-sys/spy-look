from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


_HEADING_RE = re.compile(r"^(\s{0,3})(#{1,6})\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^\s*```")
_EXISTING_NUMBER_RE = re.compile(
    r"^\s*(?:"
    r"(?:\d+|[A-Za-z]+|[ivxlcdmIVXLCDM]+|[一二三四五六七八九十百千万零〇两]+)"
    r"(?:[.)、．]|(?:\s*-\s*))?"
    r"(?:\s*\.\s*(?:\d+|[A-Za-z]+|[ivxlcdmIVXLCDM]+|[一二三四五六七八九十百千万零〇两]+))*"
    r")\s+"
)


class NumberingStyle(str, Enum):
    # 1, 2, 3
    ARABIC = "arabic"
    # I, II, III
    ROMAN = "roman"
    # i, ii, iii
    ROMAN_LOWER = "roman_lower"
    # A, B, C
    ALPHA = "alpha"
    # a, b, c
    ALPHA_LOWER = "alpha_lower"
    # 一, 二, 三
    CHINESE = "chinese"


def _normalize_style(style: NumberingStyle | str | None) -> NumberingStyle:
    if isinstance(style, NumberingStyle):
        return style
    if style is None:
        return NumberingStyle.ARABIC
    value = style.strip().lower()
    for item in NumberingStyle:
        if item.value == value:
            return item
    return NumberingStyle.ARABIC


def _to_roman(value: int) -> str:
    if value <= 0:
        return str(value)
    mapping = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    result = []
    remain = value
    for unit, token in mapping:
        while remain >= unit:
            result.append(token)
            remain -= unit
    return "".join(result)


def _to_alpha(value: int) -> str:
    if value <= 0:
        return str(value)
    chars = []
    remain = value
    while remain > 0:
        remain -= 1
        chars.append(chr(ord("A") + (remain % 26)))
        remain //= 26
    return "".join(reversed(chars))


def _to_chinese(value: int) -> str:
    if value <= 0:
        return str(value)
    digits = "零一二三四五六七八九"
    units = ["", "十", "百", "千"]
    if value < 10:
        return digits[value]
    if value < 10000:
        parts: list[str] = []
        s = str(value)
        length = len(s)
        for idx, ch in enumerate(s):
            d = int(ch)
            pos = length - idx - 1
            if d == 0:
                if parts and parts[-1] != digits[0]:
                    parts.append(digits[0])
                continue
            parts.append(digits[d] + units[pos])
        text = "".join(parts).rstrip(digits[0])
        text = text.replace("一十", "十")
        return text
    return str(value)


def _format_counter(value: int, style: NumberingStyle | str | None) -> str:
    normalized = _normalize_style(style)
    if normalized == NumberingStyle.ARABIC:
        return str(value)
    if normalized == NumberingStyle.ROMAN:
        return _to_roman(value)
    if normalized == NumberingStyle.ROMAN_LOWER:
        return _to_roman(value).lower()
    if normalized == NumberingStyle.ALPHA:
        return _to_alpha(value)
    if normalized == NumberingStyle.ALPHA_LOWER:
        return _to_alpha(value).lower()
    if normalized == NumberingStyle.CHINESE:
        return _to_chinese(value)
    return str(value)


@dataclass
class HeadingNumberingConfig:
    """Markdown 标题编号配置。"""

    # 从几级标题开始编号（1-6），例如 2 表示从 "##" 开始编号。
    start_level: int = 1
    # 编号作用到几级标题（1-6），必须 >= start_level。
    end_level: int = 6
    # 多级编号之间的分隔符，例如 "." -> "1.2.3"；"-" -> "1-2-3"。
    level_separator: str = "."
    # 整体编号末尾后缀，例如 "." -> "1.2."；"" -> "1.2"。
    number_suffix: str = "."
    # 最终标题渲染模板，{number} 是编号，{title} 是原标题。
    heading_template: str = "{number} {title}"
    # 默认编号风格（可传 NumberingStyle 或字符串，如 "arabic"）。
    default_style: NumberingStyle | str = NumberingStyle.ARABIC
    # 按标题级别覆盖风格，例如 {2: ROMAN, 3: ALPHA_LOWER}。
    level_styles: dict[int, NumberingStyle | str] = field(default_factory=dict)
    # 是否移除标题里已有编号前缀（如 "1.2 xxx" -> "xxx" 后再重新编号）。
    strip_existing_number: bool = True

    def normalized(self) -> "HeadingNumberingConfig":
        start = max(1, min(6, self.start_level))
        end = max(start, min(6, self.end_level))
        return HeadingNumberingConfig(
            start_level=start,
            end_level=end,
            level_separator=self.level_separator,
            number_suffix=self.number_suffix,
            heading_template=self.heading_template,
            default_style=_normalize_style(self.default_style),
            level_styles={
                k: _normalize_style(v) for k, v in self.level_styles.items() if 1 <= k <= 6
            },
            strip_existing_number=self.strip_existing_number,
        )


def _render_number(level: int, counters: list[int], config: HeadingNumberingConfig) -> str:
    start = config.start_level
    parts: list[str] = []
    for lv in range(start, level + 1):
        value = counters[lv]
        if value <= 0:
            continue
        style = config.level_styles.get(lv, config.default_style)
        parts.append(_format_counter(value, style))
    return config.level_separator.join(parts) + config.number_suffix


def _clean_heading_title(title: str, strip_existing_number: bool) -> str:
    cleaned = title.strip()
    cleaned = re.sub(r"\s*#+\s*$", "", cleaned).strip()
    if strip_existing_number:
        cleaned = _EXISTING_NUMBER_RE.sub("", cleaned).strip()
    return cleaned


def add_heading_numbering(markdown_text: str, config: HeadingNumberingConfig | None = None) -> str:
    """
    为 Markdown 文档标题添加层级编号。

    参数:
    - markdown_text: 原始 Markdown 文本。
    - config: 编号配置，支持起始级别、样式、模板等。

    返回:
    - 处理后的 Markdown 文本。
    """
    if not markdown_text:
        return markdown_text

    cfg = (config or HeadingNumberingConfig()).normalized()
    counters = [0] * 7  # 下标 1-6 对应 H1-H6
    in_code_block = False
    output_lines: list[str] = []

    for line in markdown_text.splitlines():
        if _FENCE_RE.match(line):
            in_code_block = not in_code_block
            output_lines.append(line)
            continue

        if in_code_block:
            output_lines.append(line)
            continue

        match = _HEADING_RE.match(line)
        if not match:
            output_lines.append(line)
            continue

        indent, marks, raw_title = match.groups()
        level = len(marks)

        if level < cfg.start_level or level > cfg.end_level:
            output_lines.append(line)
            continue

        counters[level] += 1
        for lv in range(level + 1, 7):
            counters[lv] = 0

        clean_title = _clean_heading_title(raw_title, cfg.strip_existing_number)
        number_text = _render_number(level, counters, cfg)
        new_title = cfg.heading_template.format(number=number_text, title=clean_title)
        output_lines.append(f"{indent}{marks} {new_title}".rstrip())

    return "\n".join(output_lines)

