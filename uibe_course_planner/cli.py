"""命令行入口：ucourse validate / table / fit / compare / parse。

纯离线工具：不做自动抢课、不连接教务系统——先规划好，再去教务系统选。
"""

from __future__ import annotations

from __future__ import annotations

import argparse
import json
import sys

from uibe_course_planner.model import (find_conflicts, fit_classes,
                                       load_catalog, load_plan,
                                       load_requirements, parse_sessions_text,
                                       requirement_report, credit_stats)
from uibe_course_planner.table import render_html, render_terminal


def _load_classes(args) -> tuple[list[ClassInfo], list[ClassInfo] | None]:
    """返回 (方案课程, 目录)。"""
    catalog = load_catalog(args.catalog) if getattr(args, "catalog", None) else None
    classes = load_plan(args.plan, catalog)
    return classes, catalog


def cmd_validate(args) -> int:
    classes, catalog = _load_classes(args)
    conflicts = find_conflicts(classes)
    print(f"方案共 {len(classes)} 门课 · "
          f"{credit_stats(classes)['total_credits']:g} 学分")
    if conflicts:
        print(f"\n✗ 发现 {len(conflicts)} 处时间冲突：")
        for c in conflicts:
            print(f"  · {c['a']}  ⇄  {c['b']}")
            for d in c["detail"]:
                print(f"      {d}")
    else:
        print("✓ 无时间冲突")
    if args.requirements:
        reqs = load_requirements(args.requirements)
        rows = requirement_report(classes, reqs)
        print("\n培养方案对照（已选 / 要求）：")
        for r in rows:
            mark = "✓" if r["ok"] else "✗"
            req = "-" if r["required"] is None else f"{r['required']:g}"
            gap = "" if not r["gap"] else f"（还差 {r['gap']:g}）"
            print(f"  {mark} {r['category']}: {r['selected']:g} / {req} 学分{gap}")
    return 1 if conflicts and not args.allow_conflict else 0


def cmd_table(args) -> int:
    classes, catalog = _load_classes(args)
    print(render_terminal(classes))
    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(render_html(classes, title=getattr(args, "title", None)
                                or "我的选课方案"))
        print(f"\n✓ 已导出 {args.html}")
    return 0


def cmd_fit(args) -> int:
    catalog = load_catalog(args.catalog)
    locked = (load_plan(args.locked, catalog)
              if getattr(args, "locked", None) else [])
    suggestions = fit_classes(catalog, locked)
    if not suggestions:
        print("没有需要挑选班次的课程。")
        return 0
    for s in suggestions:
        free = s["conflict_free"]
        tag = f"{len(free)}/{s['total_classes']}"
        print(f"\n{ s['name']}（无冲突班次 {tag}）")
        for o in free:
            times = "、".join(o["sessions"]) or "（无固定时间）"
            teacher = f" · {o['teacher']}" if o["teacher"] else ""
            print(f"  · {o['key']} {o['credits']:g} 学分{teacher} · {times}")
        if not free:
            print("  × 所有班次都与已锁课程冲突，需要调整锁定方案")
    return 0


def cmd_compare(args) -> int:
    plans = []
    for path in args.plans:
        catalog = load_catalog(args.catalog) if getattr(args, "catalog", None) else None
        classes = load_plan(path, catalog)
        conflicts = find_conflicts(classes)
        stats = credit_stats(classes)
        busy_days = sorted({s.day for c in classes for s in c.sessions})
        latest = max((s.end for c in classes for s in c.sessions), default=0)
        earliest = min((s.start for c in classes for s in c.sessions),
                       default=0)
        plans.append({
            "path": path, "classes": classes, "conflicts": conflicts,
            "stats": stats, "busy_days": busy_days,
            "earliest": earliest, "latest": latest,
        })

    def score(p) -> tuple:
        return (len(p["conflicts"]), -p["stats"]["total_credits"],
                len(p["busy_days"]), p["latest"])

    ranked = sorted(plans, key=score)
    width = max(len(p["path"]) for p in ranked) + 2
    print(f"{'方案':<{width}}{'冲突':>4}{'学分':>7}{'课数':>4}{'在校天':>6}"
          f"{'最早':>6}{'最晚':>6}")
    for p in ranked:
        days = "、".join(str(d) for d in p["busy_days"]) or "-"
        print(f"{p['path']:<{width}}{len(p['conflicts']):>4}"
              f"{p['stats']['total_credits']:>7g}"
              f"{p['stats']['course_count']:>4}{len(p['busy_days']):>6}"
              f"{p['earliest']:>6}{p['latest']:>6}")
    best = ranked[0]
    print(f"\n推荐：{best['path']}"
          f"（0 冲突、学分满足度优先、在校天数与最晚课时更少）"
          if not best["conflicts"] else
          f"\n⚠ 所有方案都有冲突，优先处理 {best['path']} 的 "
          f"{len(best['conflicts'])} 处冲突")
    return 0


def cmd_parse(args) -> int:
    sessions = parse_sessions_text(args.text)
    if not sessions:
        print("未识别到上课时间。示例：周一3-4节；周三 5,6节", file=sys.stderr)
        return 1
    print(json.dumps([{"day": s.day, "start": s.start, "end": s.end}
                      for s in sessions], ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ucourse",
        description="贸大选课助手：冲突检测 / 学分统计 / 课表预览 / 班次推荐（离线工具，不代选课）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="检查方案：时间冲突 + 培养方案学分对照")
    p.add_argument("plan", help="选课方案 JSON")
    p.add_argument("--catalog", help="课程目录 JSON（方案用 select 引用时必需）")
    p.add_argument("--requirements", help="培养方案学分要求 JSON（可选）")
    p.add_argument("--allow-conflict", action="store_true",
                   help="有冲突也返回退出码 0")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("table", help="渲染周课表（终端 + 可选 HTML 导出）")
    p.add_argument("plan", help="选课方案 JSON")
    p.add_argument("--catalog", help="课程目录 JSON（可选）")
    p.add_argument("--html", help="导出 HTML 文件路径（可选）")
    p.add_argument("--title", help="HTML 页面标题")
    p.set_defaults(func=cmd_table)

    p = sub.add_parser("fit", help="班次推荐：列出与已锁定课程不冲突的班次")
    p.add_argument("catalog", help="课程目录 JSON")
    p.add_argument("--locked", help="已锁定课程 JSON（如必修课方案）")
    p.set_defaults(func=cmd_fit)

    p = sub.add_parser("compare", help="多方案对比：冲突/学分/在校天数一目了然")
    p.add_argument("plans", nargs="+", help="多个选课方案 JSON")
    p.add_argument("--catalog", help="课程目录 JSON（方案用 select 引用时必需）")
    p.set_defaults(func=cmd_compare)

    p = sub.add_parser("parse", help="把「周一3-4节；周三 5,6节」文本转成 JSON")
    p.add_argument("text")
    p.set_defaults(func=cmd_parse)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
