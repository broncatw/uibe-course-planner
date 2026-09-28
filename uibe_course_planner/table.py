"""课表渲染：终端周网格 + HTML 导出。

节次对应时间（如第 1 节几点开始）因学校每学年安排可能调整，
本工具内置通用模板并允许在目录文件的 "periods" 里覆盖。
"""

from __future__ import annotations

import html
import unicodedata

from uibe_course_planner.model import DAY_NAMES, ClassInfo

#: 默认节次-时间表（可在目录文件 "periods" 覆盖：{"1": ["08:00", "08:45"], ...}）
DEFAULT_PERIODS = {
    "1": ("08:00", "08:45"), "2": ("08:55", "09:40"),
    "3": ("10:10", "10:55"), "4": ("11:05", "11:50"),
    "5": ("14:00", "14:45"), "6": ("14:55", "15:40"),
    "7": ("16:00", "16:45"), "8": ("16:55", "17:40"),
    "9": ("18:30", "19:15"), "10": ("19:25", "20:10"),
    "11": ("20:20", "21:05"), "12": ("21:15", "22:00"),
}


def _display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1
               for ch in text)


def _pad(text: str, width: int) -> str:
    gap = width - _display_width(text)
    return text + " " * max(gap, 0)


def _truncate(text: str, width: int) -> str:
    """按显示宽度截断（中文占 2 列）。"""
    out: list[str] = []
    used = 0
    for ch in text:
        w = 2 if unicodedata.east_asian_width(ch) in "WF" else 1
        if used + w > width:
            break
        out.append(ch)
        used += w
    return "".join(out)


def _occupied(classes: list[ClassInfo]) -> dict[tuple[int, int], list[str]]:
    """(day, period) -> [课程名...]。区间课占用每一节。"""
    grid: dict[tuple[int, int], list[str]] = {}
    for c in classes:
        for s in c.sessions:
            for p in range(s.start, s.end + 1):
                grid.setdefault((s.day, p), []).append(c.name)
    return grid


def render_terminal(classes: list[ClassInfo],
                    periods: dict | None = None,
                    max_period: int = 12) -> str:
    periods = {**DEFAULT_PERIODS, **(periods or {})}
    grid = _occupied(classes)
    highest = max((s.end for c in classes for s in c.sessions), default=0)
    max_period = max(max_period, highest)
    day_width = 14
    header = _pad("节次", 10) + "".join(
        _pad(DAY_NAMES[d], day_width) for d in range(1, 8))
    lines = [header, "-" * _display_width(header)]
    for p in range(1, max_period + 1):
        if not any(grid.get((d, p)) for d in range(1, 8)):
            continue
        start = periods.get(str(p), ("--:--", "--:--"))[0]
        row = _pad(f"{p:>2} {start}", 10)
        for d in range(1, 8):
            names = grid.get((d, p), [])
            cell = "/".join(dict.fromkeys(names)) if names else ""
            row += _pad(_truncate(cell, 12), day_width)
        lines.append(row)
    return "\n".join(lines)


def render_html(classes: list[ClassInfo],
                periods: dict | None = None,
                max_period: int = 12,
                title: str = "我的选课方案") -> str:
    periods = {**DEFAULT_PERIODS, **(periods or {})}
    grid = _occupied(classes)
    palette = ["#4f8cff", "#34c98e", "#ffb84f", "#c792ea",
               "#ff8a80", "#80deea", "#aed581", "#f48fb1"]
    color = {}
    for c in classes:
        color.setdefault(c.name, palette[len(color) % len(palette)])

    def cell(day: int, p: int) -> str:
        names = grid.get((day, p), [])
        if not names:
            return "<td></td>"
        unique = list(dict.fromkeys(names))
        inner = "<br>".join(
            f'<span style="color:{color[n]}">●</span> {html.escape(n)}'
            for n in unique)
        return f"<td>{inner}</td>"

    rows = []
    for p in range(1, max_period + 1):
        if not any(grid.get((d, p)) for d in range(1, 8)):
            continue
        t = periods.get(str(p), ("--:--", "--:--"))
        rows.append(
            f"<tr><th>{p}<br><small>{t[0]}–{t[1]}</small></th>"
            + "".join(cell(d, p) for d in range(1, 8)) + "</tr>")

    legend = " ".join(
        f'<span style="color:{color[n]}">●</span> {html.escape(n)}'
        for n in color)
    credits = sum(c.credits for c in classes)
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: "Microsoft YaHei", system-ui, sans-serif;
       background: #0f1420; color: #e8edf5; padding: 24px;
       max-width: 1080px; margin: 0 auto; }}
h1 {{ font-size: 20px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #2c3a55; padding: 8px; text-align: center;
          font-size: 13px; min-width: 90px; }}
th {{ color: #8b97ad; background: #1a2233; }}
td {{ height: 40px; }}
.legend {{ margin: 12px 0; font-size: 14px; }}
.sum {{ color: #8b97ad; font-size: 13px; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="sum">共 {len(classes)} 门课 · {credits:g} 学分 · 由 uibe-course-planner 生成</div>
<div class="legend">{legend}</div>
<table><tr><th>节次</th>{"".join(f"<th>{DAY_NAMES[d]}</th>" for d in range(1, 8))}</tr>
{''.join(rows)}
</table></body></html>"""
