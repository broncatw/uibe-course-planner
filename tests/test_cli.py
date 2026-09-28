"""CLI 集成测试：使用 examples/ 示例数据走完整流程。"""

import json
from pathlib import Path

import pytest

from uibe_course_planner.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
CATALOG = str(EXAMPLES / "catalog.example.json")
REQUIREMENTS = str(EXAMPLES / "requirements.example.json")


@pytest.fixture
def plan_with_conflict(tmp_path) -> str:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps({
        "select": ["计量经济学@01", "中级财务会计@01",
                   "英语言语交际@01", "Python程序设计@01"]}),
        encoding="utf-8")
    return str(path)


@pytest.fixture
def plan_clean(tmp_path) -> str:
    path = tmp_path / "clean.json"
    path.write_text(json.dumps({
        "select": ["计量经济学@01", "中级财务会计@01",
                   "英语言语交际@02", "Python程序设计@01"]}),
        encoding="utf-8")
    return str(path)


def test_validate_detects_conflict(plan_with_conflict, capsys):
    """英语@01（周一4-5节）同时撞计量@01（第4节）和财会@01（第5节）。"""
    code = main(["validate", plan_with_conflict, "--catalog", CATALOG])
    out = capsys.readouterr().out
    assert code == 1
    assert "发现 2 处时间冲突" in out
    assert "英语言语交际@01" in out
    assert "中级财务会计@01" in out


def test_validate_clean_plan_with_requirements(plan_clean, capsys):
    code = main(["validate", plan_clean, "--catalog", CATALOG,
                 "--requirements", REQUIREMENTS])
    out = capsys.readouterr().out
    assert code == 0
    assert "无时间冲突" in out
    assert "培养方案对照" in out
    assert "还差" in out                      # 示例要求远大于所选，必有缺口


def test_table_and_html_export(plan_clean, tmp_path, capsys):
    html_path = tmp_path / "table.html"
    code = main(["table", plan_clean, "--catalog", CATALOG,
                 "--html", str(html_path)])
    assert code == 0
    assert "计量经济学" in capsys.readouterr().out
    content = html_path.read_text(encoding="utf-8")
    assert "Python程序设计" in content
    assert content.strip().endswith("</html>")


def test_fit_lists_conflict_free_classes(capsys):
    locked = tmp_lock()
    code = main(["fit", CATALOG, "--locked", locked])
    out = capsys.readouterr().out
    assert code == 0
    assert "计量经济学" in out
    assert "无冲突班次" in out


def tmp_lock() -> str:
    import tempfile
    fd = tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                     delete=False, encoding="utf-8")
    json.dump({"classes": [
        {"name": "体育", "class_no": "01", "credits": 1,
         "sessions": [{"day": 1, "start": 3, "end": 4}]}]},
        fd, ensure_ascii=False)
    fd.close()
    return fd.name


def test_compare_ranks_plans(plan_with_conflict, plan_clean, capsys):
    code = main(["compare", plan_with_conflict, plan_clean,
                 "--catalog", CATALOG])
    out = capsys.readouterr().out
    assert code == 0
    assert "推荐" in out
    # 干净方案应排在冲突方案之前（表格首行数据为推荐项）
    lines = [l.strip() for l in out.splitlines() if ".json" in l]
    assert lines[0].startswith(plan_clean)


def test_parse_outputs_json(capsys):
    code = main(["parse", "周一3-4节；周五 9,10节"])
    out = capsys.readouterr().out
    assert code == 0
    data = json.loads(out)
    assert data == [{"day": 1, "start": 3, "end": 4},
                    {"day": 5, "start": 9, "end": 10}]


def test_missing_catalog_for_select_plan(tmp_path, capsys):
    sel = tmp_path / "sel.json"
    sel.write_text(json.dumps({"select": ["甲@01"]}), encoding="utf-8")
    code = main(["validate", str(sel)])
    assert code == 2
    assert "错误" in capsys.readouterr().err
