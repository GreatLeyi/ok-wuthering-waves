# Project Overview — ok-wuthering-waves (ok-ww)

> 面向 AI 的项目速览。读完本篇后，你应当能定位文件、判断该改哪里、并知道在哪些钩子里挂逻辑。

## 1. 这个项目是什么

- **定位**：基于 **图像识别 + Windows 输入模拟** 的《鸣潮》(Wuthering Waves) PC 客户端自动化辅助工具。
- **核心保证**：完全通过 Windows 接口模拟玩家操作（PostMessage + 截屏），**不读内存、不修改游戏文件**。
- **底层框架**：[`ok-script`](https://github.com/ok-oldking/ok-script) (PyPI 包)。本仓库是该框架的一个 *app*：提供配置、任务列表、场景类，框架负责截屏、特征匹配、OCR、GUI、日志、调度。
- **平台**：Windows（依赖 `pywin32`、WGC/BitBlt 截屏、PostMessage）。
- **Python**：仅支持 **3.12**（见 `pyappify.yml: requires_python`）。
- **GUI**：PySide6 + qfluentwidgets。
- **打包**：[`pyappify`](https://pypi.org/project/pyappify/) → 输出 `ok-ww-win32-{China,Global}-setup.exe`（CI: `.github/workflows/build.yml`）。

## 2. 顶层目录速查

```
ok-wuthering-waves/
├── main.py                     # Release 入口：from config; OK(config).start()
├── main_debug.py               # Debug 入口：config['debug']=True
├── config.py                   # 全局 config 字典：tasks/scene/window/i18n/ocr/template_matching
├── setup.py                    # cythonize src/*.pyx (.pyx 在 .gitignore 中，发行时才生成)
├── requirements.in             # 顶层依赖
├── requirements.txt            # pip-compile 锁定版本（实际安装用这个）
├── requirements-dev.txt        # 开发依赖
├── pyappify.yml                # 打包配置：China / Global / Debug 三个 profile
├── deploy.txt                  # CI 同步到下游 update 仓库的文件白名单
├── run_tests.ps1               # PowerShell 跑 tests/*.py 的脚本
├── AGENTS.md                   # 全局 agent 注意：用 .venv 跑 python
├── README.md / README_en.md    # 用户文档（面向人类）
├── readme/                     # README 用到的图片 + faq.md
│
├── src/                        # ★ 业务代码全在这里
│   ├── __init__.py             #   text_white_color 常量（OCR 白色文本范围）
│   ├── globals.py              #   Globals(QObject)：懒加载 YOLO 模型
│   ├── Labels.py               #   ★ 所有视觉特征名的 StrEnum（assets/coco_annotations.json 的 categories）
│   ├── OnnxYolo8Detect.py      #   ONNX Runtime YOLOv8 推理（声骸检测）
│   ├── OpenVinoYolo8Detect.py  #   OpenVINO YOLOv8 推理（CPU/NPU 优先时走这条）
│   ├── scene/WWScene.py        #   场景对象，缓存 in_team / in_combat 等本帧状态
│   ├── combat/CombatCheck.py   #   战斗状态检测、boss 血量、f 打断、复活检测
│   ├── char/                   #   ★ 每个游戏角色一个 .py
│   │   ├── BaseChar.py         #     角色基类（951 行）：技能可用性、CD、协奏值、切人优先级、回合循环
│   │   ├── Healer.py           #     治疗位基类（覆盖 do_get_switch_priority）
│   │   ├── CharFactory.py      #     ★ 注册表：Labels.<char_xxx> -> {cls, res_cd, echo_cd, liberation_cd, ring_index}
│   │   └── Verina.py / Camellya.py / ...  各角色实现 do_perform()
│   └── task/                   #   ★ 每个自动化任务一个 .py
│       ├── BaseWWTask.py       #     任务基类（1193 行）：地图缩放、走到目标、F 拾取、月卡、登录流程
│       ├── BaseCombatTask.py   #     战斗任务基类（900 行）：load_chars、combat_once、switch_next_char、复活
│       ├── WWOneTimeTask.py    #     一次性任务的 mixin（先做 MouseReset 再激活窗口）
│       ├── SkipBaseTask.py     #     跳剧情共用逻辑
│       ├── DailyTask.py        #     一条龙：登录→月卡→F2 周本→刷副本→领日常→领邮件→战令
│       ├── MultiAccountDailyTask.py  多账号一条龙
│       ├── FarmEchoTask.py     #     刷声骸（最大文件之一）
│       ├── AutoRogueTask.py    #     无音清剿（半自动 rogue）
│       ├── ForgeryTask.py      #     模拟领域 / 凝素领域
│       ├── NightmareNestTask.py
│       ├── SimulationTask.py
│       ├── TacetTask.py        #     残象抑制
│       ├── EnhanceEchoTask.py / ChangeEchoTask.py / FiveToOneTask.py / DiagnosisTask.py
│       ├── DomainTask.py / FarmMapTask.py
│       ├── AutoCombatTask.py   #     ★ TriggerTask：进入战斗时自动循环 perform
│       ├── AutoPickTask.py     #     TriggerTask：扫到 F 提示就拾取（白/黑名单）
│       ├── SkipDialogTask.py   #     TriggerTask：跳剧情
│       ├── AutoLoginTask.py    #     TriggerTask：登录界面自动点击
│       ├── MouseResetTask.py   #     TriggerTask：游戏抢鼠标时把鼠标移回去
│       ├── FastTravelTask.py   #     TriggerTask：地图传送
│       └── process_feature.py  #     特定特征（如 illusive_realm_exit）的图像预处理
│
├── tests/                      # unittest，走 ok.test.TaskTestCase（注入图片做断言）
├── assets/
│   ├── coco_annotations.json   # ★ 视觉特征定义（id/name/bbox），与 Labels.py 对应
│   ├── images/                 # 与 annotations 对应的模板图（0.png, 1.png, ...）
│   └── echo_model/echo.onnx    # 声骸 YOLO 模型
├── ok_templates/               # ★ git submodule —— X-AnyLabeling 工程，标注源文件
│                               #     仓库说明：标注后跑 compress.py，自动写入 assets/images/
├── i18n/                       # gettext: es_ES / ja_JP / ko_KR / zh_CN / zh_TW
├── icons/, icon.png, icon.ico  # 图标
├── .agent/skills/              # ★ 已有的 AI 技能（详见 ai-doc/README.md）
└── .github/workflows/          # CI：build / test / ai_code_review / sign_exe / mirrorchyan_*
```

## 3. 启动流程（最短路径）

```python
# main.py
from config import config
from ok import OK
OK(config).start()
```

`OK(config).start()` 由 `ok-script` 提供，做的事大致是：

1. 读 `config.py` 里的 `windows`、`window_size`、`supported_resolution` → 找鸣潮窗口、设置截屏方式（WGC 优先，回退 BitBlt）。
2. 读 `template_matching.coco_feature_json` → 加载 `assets/coco_annotations.json` 描述的所有特征（与 `Labels` 一一对应）。
3. 读 `ocr` → 初始化 onnxocr-ppocrv5（可启用 OpenVINO/NPU）。
4. 读 `my_app: ['src.globals', 'Globals']` → 实例化 `Globals`（懒加载 echo YOLO 模型）。
5. 读 `scene` → 实例化 `WWScene`，每帧重置缓存。
6. 读 `onetime_tasks` 与 `trigger_tasks` 列表 → 按顺序实例化所有任务。
7. 启动 GUI（`use_gui: True`）；命令行 `-t N` 自动开第 N 个 onetime task，`-e` 完成后退出。

## 4. 任务系统：两类，记牢

| 类别 | 父类 | 行为 | 例子 |
| --- | --- | --- | --- |
| **One-time Task** | `BaseTask`（在本仓中通常套 `BaseCombatTask` + `WWOneTimeTask`） | 用户点"开始"才跑，`run()` 返回即结束并自动 disable | `DailyTask`、`FarmEchoTask`、`ForgeryTask`、`AutoRogueTask`、`TacetTask`、`SimulationTask`、`NightmareNestTask`、`EnhanceEchoTask`、`ChangeEchoTask`、`DiagnosisTask`、`MultiAccountDailyTask` |
| **Trigger Task** | `TriggerTask` + 项目基类 | 后台按 `trigger_interval` 不断轮询 `run()`，返回 truthy 表示这一轮处理过 | `AutoCombatTask`（0.1s）、`AutoPickTask`、`AutoDialogTask`（0.5s）、`AutoLoginTask`（5s）、`MouseResetTask`（10s）、`FastTravelTask` |

注册位置：`config.py` 中的 `onetime_tasks` / `trigger_tasks` 列表，元素是 `["src.task.<Module>", "<ClassName>"]`。

每个任务的 GUI 元数据由 `__init__` 决定：`name` / `description` / `icon` / `group_name` / `group_icon` / `default_config` / `config_description` / `config_type`（dropdown 等）/ `supported_languages`。

## 5. 战斗系统：怎么打怪

调用链：

```
AutoCombatTask.run()  (TriggerTask, every 0.1s)
  └─ in_combat()  (CombatCheck)
       └─ True → load_chars() (BaseCombatTask)
                   └─ for i in 0..2:
                        get_char_by_pos(box=char_i)  ← src/char/CharFactory.py
                          └─ 在屏幕角色头像位置上模板匹配 Labels.char_*
                          └─ 返回对应 BaseChar 子类实例
                 → while in_combat():
                      get_current_char().perform()
                        └─ do_fast_perform() / do_perform()  ← 每个角色覆写
```

切人由 `BaseCombatTask.switch_next_char()` 根据 `Priority` 决定：

- `MAX/FAST_SWITCH/SKILL_AVAILABLE` → 谁可用谁上
- `CURRENT_CHAR` 是个负值 → 默认不留在原地，除非别人都不行
- 同优先级看 `last_perform`，越久没动手的越优先

技能名是固定的英文术语（**别用中文**）：`resonance` / `echo` / `liberation` / `forte`。

## 6. 视觉识别：三条路

| 方法 | 何时用 | 调用 |
| --- | --- | --- |
| **模板匹配** | UI 元素、固定图标 | `self.find_one('<label>', threshold=0.8, box=...)` —— label 必须存在于 `Labels.py` 与 `coco_annotations.json` |
| **OCR** | 文本（数字、按钮文字、对话） | `self.ocr(x1,y1,x2,y2, match=re_or_text)` / `self.wait_ocr(..., raise_if_not_found=False)` —— 库是 `onnxocr-ppocrv5`，会自动繁→简 |
| **YOLO** | 仅声骸 | `og.my_app.yolo_detect(frame, threshold=0.5, label=0)`（封装在 `BaseWWTask.find_echos()`） |

新增视觉特征的流程：

1. 在 `ok_templates/` (submodule) 里用 X-AnyLabeling 标注。
2. 跑 submodule 里的 `compress.py` → 自动写入 `assets/images/<n>.png` + 更新 `assets/coco_annotations.json`。
3. 在 `src/Labels.py` 里加一行枚举值（**值 = `coco_annotations.json` 中的 `name`**）。

> AI 协助开发时：**绝不允许凭空捏造 Labels 名**。如果代码需要新特征，明确告诉用户该特征要叫什么、要在哪里用，由开发者去标注；不要 silent 加 enum。

## 7. 配置（config）

- 全局可调项在 `config.py` 顶部用 `ConfigOption('Group Name', {...defaults}, description=...)` 声明，会出现在 GUI 设置里：
  - `Game Hotkey Config`：游戏内技能键位（玩家如果改键，要在这里同步）。
  - `Character Config`：`Iuno C6` / `Verina C2` / `Chisa DPS` 这种与角色命途/共鸣链相关的开关。
  - `Pick Echo Config`：声骸拾取是否用 OCR。
  - `Monthly Card Config`：月卡时间（避免被弹窗打断任务）。
- 每个 task 自己的配置在它 `__init__` 里通过 `self.default_config` / `self.config_type` / `self.config_description` 暴露。
- 用户改过的值落盘到 `configs/`（在 `.gitignore` 中）。

## 8. 国际化（i18n）

- 框架走 **gettext**：`i18n/<locale>/LC_MESSAGES/ok.po` → 编译成 `ok.mo`。
- 已存在的 locale：`zh_CN` / `zh_TW` / `ja_JP` / `ko_KR` / `es_ES`。`en_US` 是源语言，**不存在于 `i18n/`** 而是从代码字面量里取（`.gitignore` 中显式忽略 `i18n/en_US/`）。
- 需要本地化的字符串：`name` / `description` / `default_config` 的字符串值 / `config_description` / `config_type` 的下拉选项 / 用户可见的 OCR 匹配文本。
- **不要本地化 `default_config` 的 key**（key 持久化为 JSON）。
- 添加翻译的工具：`.agent/skills/ok-script-i18n/scripts/task_i18n_helper.py`（scan / check / compile）。

## 9. 跑代码与测试

```powershell
# 安装/更新依赖
pip install -r requirements.txt --upgrade

# 跑程序
python main.py            # release
python main_debug.py      # debug（截屏更多）

# 跑测试（推荐用本仓里 .venv 的解释器）
.\.venv\Scripts\python.exe -m unittest discover tests
# 或者直接：
.\run_tests.ps1
```

测试用 `ok.test.TaskTestCase`，可以用 `self.set_image('tests/images/xxx.png')` 注入截图来跑断言。新增视觉/可用性逻辑时，请同步加 / 改 `tests/Test*.py`。

## 10. CI / 发布

- **触发**：push tag `v*` 时跑 `.github/workflows/build.yml` → 跑全部 `tests/` → 用 `pyappify-action` 打包出 `ok-ww-win32-{China,Global}-setup.exe` → release。
- **签名**：当 tag 是 `v\d+\.\d+\.\d+` 且 `SIGN_BUILD=true` 时，调用 SignPath.io 签名（`sign_exe.yml`）。
- **同步**：`partial-sync-repo` 把 `deploy.txt` 列出的文件同步到 `cnb.cool` 镜像和 `ok-ww-update` 下游仓库（用户更新走那边）。

## 11. AI 修改本仓时的硬性约束

读完上面已经够了。再加几条防止常见错误：

1. **创建/修改角色** → 走 `.agent/skills/ok-ww-characters/`，必须在 `CharFactory.py` 注册，否则永远不会被实例化。
2. **创建/修改任务** → 走 `.agent/skills/ok-script-tasks/`，必须在 `config.py` 的 `onetime_tasks` 或 `trigger_tasks` 中注册。
3. **新增视觉特征 / Labels 枚举** → 不能凭空添加。明确告诉用户需要哪个 label，模板标注由用户在 `ok_templates/` 子模块完成。
4. **跑 Python** → 优先使用 `.\.venv\Scripts\python.exe`（Windows）或 `./.venv/bin/python`（POSIX），见 `AGENTS.md`。
5. **不要写中文配置 key**。配置 key 是英文持久化字符串，中文走 i18n 或 `config_description`。
6. **不要把 `default_config['_enabled']`** 漏掉用户预期默认开启的 trigger task。
7. **战斗循环不要 hot loop**：要么 `self.next_frame()`，要么 `self.sleep(...)`，否则会 starve 其它检测。
8. **不要 commit `configs/`、`logs/`、`screenshots/`、`click_screenshots/`** —— 已在 `.gitignore`，不要手动加。
9. **不要碰 `CLAUDE.md` 与 `.claude/`**（已在 `.gitignore`，是个人目录）。

## 12. 常见错误诊断

| 现象 | 大概率原因 | 在哪改 |
| --- | --- | --- |
| 任务找不到角色 | 角色 label 没注册到 `CharFactory.char_dict` | `src/char/CharFactory.py` |
| `find_one` 总返回 None | label 不在 `Labels.py` / `coco_annotations.json` 名字对不上 / threshold 太高 | `Labels.py` + `assets/coco_annotations.json` |
| OCR 漏字 | onnxocr 是 PP-OCRv5，繁体已自动转简体；中文字段在 OCR 后直接匹配 `re.compile(...)` | 调匹配正则 / 调 `box_of_screen()` 的范围 |
| 月卡弹窗打断任务 | `Monthly Card Config` 没设对，或者 `set_check_monthly_card()` 没在任务里调 | `BaseWWTask.set_check_monthly_card` / 任务 `__init__` |
| 切角色卡死 | `switch_char_time_out`（默认 5s）超时；可能是动画冻结没纳入 freeze_durations | `BaseCombatTask.add_freeze_duration` |
| GUI 上某 task 不显示 | 当前 game language 不在 `supported_languages` 里 | 任务 `__init__` 的 `self.supported_languages = ['zh_CN', ...]` |

## 13. 词汇表（最重要的几个）

完整术语表见 `ai-doc/glossary.md`。这里给最常踩坑的：

- **Echo** = 声骸（两层意思：① 声骸技能键 `q`；② 地图上的怪物掉落物，需要 YOLO 识别 + F 拾取）
- **Resonance** = 共鸣技能（`e`）
- **Forte** = 共鸣回路（角色专属能量条，比如 Verina 的黄色频率分析）
- **Liberation** = 共鸣解放（`r`，大招，会触发动画 freeze）
- **Concerto / Con** = 协奏值（满了可以触发入场技 intro）
- **Intro / Outro** = 入场技 / 退场技（切人时触发）
- **Realm** = 幻象空间（迷幻领域，特殊场景，combat check 会绕过部分世界检测）
