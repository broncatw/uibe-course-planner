"""选课数据模型：班次、冲突检测、学分统计、无冲突班次推荐。

设计参照高校开源选课分析工具的通用思路（冲突检测 → 预选课表 →
学分统计 → 班次筛选），完全离线、不连接教务系统、不代为选课。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

DAY_NAMES = {1: "周一", 2: "周二", 3: "周三", 4: "周四",
             5: "周五", 6: "周六", 7: "周日"}

#: 数据文件里允许的星期写法 → 数字
DAY_ALIASES = {**{n: d for d, n in DAY_NAMES.items()},
               "周一": 1, "周二": 2, "周三": 3, "周四": 4,
               "周五": 5, "周六": 6, "周日": 7,
               "星期一": 1, "星期二": 2, "星期三": 3, "星期四": 4,
               "星期五": 5, "星期六": 6, "星期日": 7, "星期天": 7}


@dataclass(frozen=True)
class Session:
    """一次上课：day 1-7（周一到周日），start/end 为节次（含两端）。"""

    day: int
    start: int
    end: int

    def overlaps(self, other: "Session") -> bool:
        return (self.day == other.day
                and self.start <= other.end and other.start <= self.end)

    def label(self) -> str:
        return f"{DAY_NAMES[self.day]}{self.start}-{self.end}节"


@dataclass(frozen=True)
class ClassInfo:
    """一个教学班（同一门课可有多个班次）。key = 课程名@班次号。"""

    name: str
    class_no: str
    credits: float
    category: str = "其他"          # 培养方案归类：专业必修/限选/通识……
    teacher: str = ""
    sessions: tuple[Session, ...] = ()
    weeks: str = ""
    note: str = ""

    @property
    def key(self) -> str:
        return f"{self.name}@{self.class_no}"

    def conflicts_with(self, other: "ClassInfo") -> list[tuple[Session, Session]]:
        return [(a, b) for a in self.sessions for b in other.sessions
                if a.overlaps(b)]


# ------------------------------------------------------------------ #
# 文件加载
# ------------------------------------------------------------------ #
def _parse_session_dict(obj: dict) -> Session:
    raw_day = str(obj.get("day", 1))
    day = DAY_ALIASES.get(raw_day)
    if day is None:
        day = int(raw_day)
    return Session(day=day, start=int(obj["start"]), end=int(obj.get("end", obj["start"])))


def _parse_class_dict(obj: dict) -> ClassInfo:
    sessions = tuple(_parse_session_dict(s) for s in obj.get("sessions", []))
    credits = float(obj.get("credits", 0))
    return ClassInfo(
        name=str(obj["name"]),
        class_no=str(obj.get("class_no", "01")),
        credits=credits,
        category=str(obj.get("category", "其他")),
        teacher=str(obj.get("teacher", "")),
        sessions=sessions,
        weeks=str(obj.get("weeks", "")),
        note=str(obj.get("note", "")),
    )


def load_json(path) -> dict:
    with open(path, "rb") as f:
        return json.load(f)


def load_catalog(path) -> list[ClassInfo]:
    """课程目录文件：{"classes": [...]}（一门课多个班次 = 多条记录）。"""
    data = load_json(path)
    return [_parse_class_dict(o) for o in data.get("classes", [])]


def load_plan(path, catalog: list[ClassInfo] | None = None) -> list[ClassInfo]:
    """选课方案文件。两种写法：
    1. 内联完整数据：{"classes": [...]}（无需 catalog）
    2. 引用目录：{"select": ["计量经济学@01", "大学英语@03"]}
    """
    data = load_json(path)
    if data.get("classes"):
        return [_parse_class_dict(o) for o in data["classes"]]
    keys = data.get("select", [])
    if not catalog:
        raise ValueError("方案用 select 引用班次，但未提供 --catalog 课程目录")
    index = {c.key: c for c in catalog}
    missing = [k for k in keys if k not in index]
    if missing:
        raise KeyError(f"课程目录中找不到班次: {', '.join(missing)}")
    return [index[k] for k in keys]


def load_requirements(path) -> dict[str, float]:
    """培养方案学分要求：{"专业必修": 30, ...}。以 _ 开头的键视为注释。"""
    data = load_json(path)
    out: dict[str, float] = {}
    for k, v in data.items():
        if str(k).startswith("_"):
            continue
        out[str(k)] = float(v)
    return out


# ------------------------------------------------------------------ #
# 冲突检测与学分统计
# ------------------------------------------------------------------ #
def find_conflicts(classes: list[ClassInfo]) -> list[dict]:
    """返回方案内所有时间冲突对。"""
    out = []
    for i, a in enumerate(classes):
        for b in classes[i + 1:]:
            hits = a.conflicts_with(b)
            if hits:
                out.append({
                    "a": a.key, "b": b.key,
                    "detail": [f"{x.label()} vs {y.label()}" for x, y in hits],
                })
    return out


def credit_stats(classes: list[ClassInfo]) -> dict:
    """按培养方案归类统计学分：各类小计 + 总学分 + 课数。"""
    by_cat: dict[str, float] = {}
    for c in classes:
        by_cat[c.category] = by_cat.get(c.category, 0) + c.credits
    total = sum(c.credits for c in classes)
    return {
        "total_credits": round(total, 1),
        "course_count": len(classes),
        "by_category": {k: round(v, 1) for k, v in sorted(by_cat.items())},
    }


def requirement_report(classes: list[ClassInfo],
                       requirements: dict[str, float]) -> list[dict]:
    """对照培养方案：每类 已选/要求/缺口。"""
    stats = credit_stats(classes)["by_category"]
    rows = []
    for cat, need in requirements.items():
        got = stats.get(cat, 0)
        rows.append({
            "category": cat, "required": need, "selected": got,
            "gap": round(max(need - got, 0), 1),
            "ok": got >= need,
        })
    for cat, got in stats.items():
        if cat not in requirements:
            rows.append({"category": cat, "required": None,
                         "selected": got, "gap": None, "ok": True})
    return rows


# ------------------------------------------------------------------ #
# 班次推荐（fit）：给已锁定课程，为剩余课程找无冲突班次
# ------------------------------------------------------------------ #
def fit_classes(catalog: list[ClassInfo],
                locked: list[ClassInfo]) -> list[dict]:
    """对目录中每门课（同名多班次），列出与已锁定课程不冲突的班次。

    返回 [{name, options: [{key, teacher, sessions}], conflict_free: n}]
    """
    suggestions = []
    names = sorted({c.name for c in catalog})
    locked_names = {c.name for c in locked}
    for name in names:
        if name in locked_names:
            continue
        all_classes = [c for c in catalog if c.name == name]
        options = []
        for c in all_classes:
            clash = any(c.conflicts_with(l) for l in locked)
            if not clash:
                options.append({
                    "key": c.key, "teacher": c.teacher,
                    "sessions": [s.label() for s in c.sessions],
                    "credits": c.credits,
                })
        if all_classes:
            suggestions.append({
                "name": name,
                "total_classes": len(all_classes),
                "conflict_free": options,
            })
    return suggestions


# ------------------------------------------------------------------ #
# 教务课表文本解析辅助：把「周一3-4节」「周三 5,6节」转成 sessions
# ------------------------------------------------------------------ #
_SEGMENT_RE = re.compile(
    r"(周一|周二|周三|周四|周五|周六|周日|星期[一二三四五六日天])\s*(\d+)\s*[-–]\s*(\d+)节?"
    r"|(周一|周二|周三|周四|周五|周六|周日|星期[一二三四五六日天])\s*([\d,\s]+)节")


def parse_sessions_text(text: str) -> list[Session]:
    """从自由文本提取上课时间。支持：
    - 区间：周一3-4节
    - 列举：周三 5,6节（连续数字自动合并为区间，跳号则拆分）
    分隔符支持中英文分号/逗号/空格/换行。
    """
    sessions: list[Session] = []
    for m in _SEGMENT_RE.finditer(text):
        if m.group(1):
            day = DAY_ALIASES[m.group(1)]
            start, end = int(m.group(2)), int(m.group(3))
            if end < start:
                start, end = end, start
            sessions.append(Session(day, start, end))
        elif m.group(4):
            day = DAY_ALIASES[m.group(4)]
            nums = sorted(int(n) for n in re.findall(r"\d+", m.group(5)))
            if not nums:
                continue
            run_start = prev = nums[0]
            for n in nums[1:]:
                if n == prev + 1:        # 连续节次合并为一个区间
                    prev = n
                    continue
                sessions.append(Session(day, run_start, prev))
                run_start = prev = n
            sessions.append(Session(day, run_start, prev))
    return sessions
