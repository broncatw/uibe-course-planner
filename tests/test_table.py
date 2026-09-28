"""渲染测试：终端网格与 HTML 导出。"""

from uibe_course_planner.model import ClassInfo, Session
from uibe_course_planner.table import render_html, render_terminal


def make():
    return [
        ClassInfo(name="计量经济学", class_no="01", credits=3,
                  category="专业必修", teacher="A",
                  sessions=(Session(1, 3, 4), Session(3, 1, 2))),
        ClassInfo(name="Python程序设计", class_no="01", credits=2,
                  category="专业限选", teacher="B",
                  sessions=(Session(5, 9, 10),)),
    ]


def test_terminal_render_contains_courses_and_days():
    text = render_terminal(make())
    assert "周一" in text and "周五" in text
    assert "计量经济学" in text
    assert "Python程" in text            # 单元格截断到 6 个显示宽度
    assert "周三" in text
    # 节次行只显示有课的行（第 1、3、4、9、10 节）
    assert " 1 08:00" in text
    assert " 9 18:30" in text


def test_terminal_render_auto_extends_period():
    classes = [ClassInfo(name="晚课", class_no="01", credits=1,
                         sessions=(Session(1, 13, 14),))]
    text = render_terminal(classes, max_period=12)
    assert "13" in text and "14" in text


def test_html_render_structure():
    html_text = render_html(make(), title="我的方案")
    assert "我的方案" in html_text
    assert "计量经济学" in html_text
    assert "共 2 门课 · 5 学分" in html_text
    assert html_text.strip().endswith("</html>")
