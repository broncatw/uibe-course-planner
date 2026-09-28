"""核心模型测试：冲突判定、学分统计、班次推荐、文件加载、文本解析。"""

import json

import pytest

from uibe_course_planner.model import (Session, ClassInfo, find_conflicts,
                                       credit_stats, requirement_report,
                                       fit_classes, load_plan, load_catalog,
                                       parse_sessions_text)


def cls(name="课程A", no="01", credits=3, category="专业必修",
        sessions=((Session(1, 3, 4),),), teacher="T"):
    return ClassInfo(name=name, class_no=no, credits=credits,
                     category=category, teacher=teacher,
                     sessions=tuple(sessions))


# ------------------------------------------------------------------ #
# 冲突判定
# ------------------------------------------------------------------ #
def test_session_overlap_edges():
    assert Session(1, 3, 4).overlaps(Session(1, 4, 5))       # 相邻节相接=冲突
    assert Session(1, 3, 4).overlaps(Session(1, 3, 4))       # 完全相同
    assert not Session(1, 3, 4).overlaps(Session(1, 5, 6))   # 不相交
    assert not Session(1, 3, 4).overlaps(Session(2, 3, 4))   # 不同天


def test_find_conflicts_pairs():
    a = cls("甲", sessions=(Session(1, 3, 4),))
    b = cls("乙", sessions=(Session(1, 4, 5),))
    c = cls("丙", sessions=(Session(5, 9, 10),))
    conflicts = find_conflicts([a, b, c])
    assert len(conflicts) == 1
    assert conflicts[0]["a"] == "甲@01" and conflicts[0]["b"] == "乙@01"
    assert "周一3-4节 vs 周一4-5节" in conflicts[0]["detail"][0]


def test_no_conflict_clean_plan():
    a = cls("甲", sessions=(Session(1, 3, 4),))
    b = cls("乙", sessions=(Session(2, 3, 4),))
    assert find_conflicts([a, b]) == []


# ------------------------------------------------------------------ #
# 学分统计与培养方案对照
# ------------------------------------------------------------------ #
def test_credit_stats():
    plan = [cls("甲", credits=3, category="专业必修"),
            cls("乙", credits=2, category="专业必修"),
            cls("丙", credits=2, category="通识选修")]
    stats = credit_stats(plan)
    assert stats["total_credits"] == 7
    assert stats["course_count"] == 3
    assert stats["by_category"] == {"专业必修": 5, "通识选修": 2}


def test_requirement_report_gap_and_extra():
    plan = [cls("甲", credits=3, category="专业必修"),
            cls("丙", credits=2, category="通识选修")]
    rows = requirement_report(plan, {"专业必修": 5, "体育": 1})
    by_cat = {r["category"]: r for r in rows}
    assert by_cat["专业必修"]["gap"] == 2
    assert by_cat["专业必修"]["ok"] is False
    assert by_cat["体育"]["gap"] == 1
    assert by_cat["通识选修"]["required"] is None       # 方案外类别只展示
    assert by_cat["通识选修"]["ok"] is True


# ------------------------------------------------------------------ #
# 班次推荐（fit）
# ------------------------------------------------------------------ #
def test_fit_classes_filters_conflicts():
    catalog = [
        cls("计量经济学", "01", sessions=(Session(1, 3, 4),)),
        cls("计量经济学", "02", sessions=(Session(2, 3, 4),)),
        cls("英语", "01", sessions=(Session(1, 4, 5),)),
    ]
    locked = [cls("体育", "01", sessions=(Session(1, 3, 4),))]
    out = {s["name"]: s for s in fit_classes(catalog, locked)}
    assert out["计量经济学"]["conflict_free"][0]["key"] == "计量经济学@02"
    assert out["英语"]["conflict_free"] == []            # 周一4节相撞
    assert "体育" not in out                              # 已锁课程不再推荐


# ------------------------------------------------------------------ #
# 文件加载
# ------------------------------------------------------------------ #
def test_load_plan_inline_and_select(tmp_path):
    inline = tmp_path / "inline.json"
    inline.write_text(json.dumps({"classes": [
        {"name": "甲", "class_no": "01", "credits": 2,
         "sessions": [{"day": "周一", "start": 1, "end": 2}]}]}),
        encoding="utf-8")
    plan = load_plan(inline)
    assert plan[0].key == "甲@01"
    assert plan[0].sessions[0].day == 1

    catalog = [cls("甲", "01"), cls("甲", "02")]
    cat_path = tmp_path / "cat.json"
    cat_path.write_text(json.dumps({"classes": [
        {"name": "甲", "class_no": "01", "credits": 3},
        {"name": "甲", "class_no": "02", "credits": 3}]}), encoding="utf-8")
    sel = tmp_path / "sel.json"
    sel.write_text(json.dumps({"select": ["甲@02"]}), encoding="utf-8")
    assert load_plan(sel, load_catalog(cat_path))[0].class_no == "02"

    with pytest.raises(KeyError):
        sel2 = tmp_path / "sel2.json"
        sel2.write_text(json.dumps({"select": ["不存在@99"]}), encoding="utf-8")
        load_plan(sel2, load_catalog(cat_path))


# ------------------------------------------------------------------ #
# 文本解析
# ------------------------------------------------------------------ #
def test_parse_sessions_text_ranges_and_lists():
    got = parse_sessions_text("周一3-4节；周三 5,6节 周日8节")
    assert got == [Session(1, 3, 4), Session(3, 5, 6), Session(7, 8, 8)]


def test_parse_sessions_text_weekday_alias_and_reversed_range():
    got = parse_sessions_text("星期五6-4节")
    assert got == [Session(5, 4, 6)]


def test_parse_sessions_text_empty():
    assert parse_sessions_text("没有时间信息") == []
