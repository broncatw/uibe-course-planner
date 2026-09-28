# uibe-course-planner · 贸大选课助手

对外经济贸易大学（UIBE）的**离线选课规划工具**：班次时间冲突检测、培养方案学分对照、周课表预览（终端 + HTML）、无冲突班次推荐、多方案对比。

**纯 Python 标准库、零依赖、离线可用、不连接教务系统、不代为选课**——先把方案规划好，再自己去教务系统选，省下选课页面上反复「加不上就换班次」的抓狂时间。

设计思路参考高校开源选课分析工具的通用模式（冲突检测 → 预选课表 → 班次筛选 → 学分统计），如 [国科大选课分析](https://github.com/gyr66/UCAS-course-choose-analysis)。

> 姊妹项目：[uibe-booker](https://github.com/broncatw/uibe-booker)（图书馆座位/研讨间预约 + 定时抢座 + 捡漏监控）

## 为什么需要它

选课系统只告诉你「这门课满了没有」，不告诉你：

- 两门课的班次在周二第 3 节撞车了，直到开学第一周才发现
- 这学期选完，培养方案还差多少学分、差在哪个类别
- 同一门课 5 个班次里，哪些和你的必修课不冲突
- 三个候选方案到底哪个更强

这些全是**离线可算**的事——这就是本工具干的活。

## 安装

```bash
pip install -e .          # 零第三方依赖
ucourse --help            # 或 python -m uibe_course_planner
```

## 快速上手

示例数据在 [examples/](./examples/)（课程/班次均为虚构示例，请按教务系统真实数据整理自己的）：

```bash
# 1. 校验方案：冲突 + 学分缺口，有冲突退出码为 1，可直接接脚本
ucourse validate examples/plan.example.json \
    --catalog examples/catalog.example.json \
    --requirements examples/requirements.example.json

# 2. 看周课表，顺手导出 HTML
ucourse table examples/plan.example.json \
    --catalog examples/catalog.example.json --html plan.html

# 3. 必修已锁定，剩下每门课还有哪些班次可选？
ucourse fit examples/catalog.example.json --locked locked.json

# 4. 两个方案摆在一起比：冲突 / 学分 / 在校天数 / 最晚课时
ucourse compare planA.json planB.json --catalog examples/catalog.example.json
```

## 数据格式

**课程目录**（一门课多个班次 = 多条记录）：

```json
{
  "classes": [
    {
      "name": "计量经济学",
      "class_no": "01",
      "credits": 3,
      "category": "专业必修",
      "teacher": "张三",
      "sessions": [{"day": "周一", "start": 3, "end": 4},
                   {"day": "周三", "start": 1, "end": 2}],
      "weeks": "1-16"
    }
  ],
  "periods": {"1": ["08:00", "08:45"]}
}
```

- `category` 用你自己培养方案的分类名（专业必修/专业限选/通识选修……），学分对照按它聚合
- `periods` 是节次-时间对照，可省略（省略时用通用模板）；写进目录文件即可让课表显示真实时间
- 课表文本里有「周一3-4节；周三 5,6节」这类描述？`ucourse parse "周一3-4节；周三 5,6节"` 直接转 JSON

**选课方案**（两种写法任选）：

```json
{"select": ["计量经济学@01", "大学英语@03"]}      // 引用目录
{"classes": [ …完整班次数据… ]}                   // 内联，无需目录
```

**培养方案要求**（可选，给 validate 做缺口计算）：

```json
{"专业必修": 55, "专业限选": 16, "通识选修": 8}
```

## 命令一览

| 命令 | 作用 | 退出码 |
|---|---|---|
| `validate` | 时间冲突 + 学分缺口 | 有冲突=1 |
| `table` | 终端周课表 + `--html` 导出 | 0 |
| `fit` | 列出与已锁定课程无冲突的班次 | 0 |
| `compare` | 多方案对比并给推荐 | 0 |
| `parse` | 「周一3-4节」文本 → sessions JSON | 识别失败=1 |

## 设计边界（重要）

- **不连接教务系统、不做自动抢课**：选课操作请在学校官方系统完成，本工具只做规划。这也意味着它永远不会因为教务系统改版而失效
- 数据需要你自己从教务系统课表页面整理成 JSON（一次性工作，整理好可复用、可分享给同学）
- 节次时间、培养方案要求默认模板/示例，请以学校最新文件为准
- 考研座位、空教室借用等需求见 [uibe-booker](https://github.com/broncatw/uibe-booker)

## 开发

```bash
pip install -e .[dev]
pytest          # 20 个测试，全离线
```

```
uibe_course_planner/
├── model.py    # 数据模型：冲突判定、学分统计、fit 推荐、文本解析
├── table.py    # 终端网格（对齐中文宽度）+ HTML 导出
└── cli.py      # argparse 命令分发
```

## License

[MIT](./LICENSE)
