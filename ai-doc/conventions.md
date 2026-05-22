# Conventions — 编码与协作约定

> 在本仓做 AI 辅助开发时的硬约束。违反这些会让 PR 直接被拒。

## 1. Python 环境

- 仅支持 **Python 3.12**（`pyappify.yml: requires_python: "3.12"`）。
- **必须用本地 venv** 跑 Python：
  - Windows / PowerShell：`.\.venv\Scripts\python.exe`
  - POSIX：`./.venv/bin/python`
  - 没有 `.venv` 才回退到全局 `python`。
- 详见 `AGENTS.md` 与 `.agent/skills/use-local-venv/SKILL.md`。

```powershell
# 推荐：直接调解释器，不要 activate
.\.venv\Scripts\python.exe -m unittest tests/TestChar.py
.\.venv\Scripts\python.exe main_debug.py
```

## 2. 依赖管理

- `requirements.in` 是**手写**的顶层依赖。
- `requirements.txt` 是 `pip-compile` 锁定后的版本，**实际安装用这个**。
- 修改依赖：先改 `requirements.in`，然后跑 `pip-compile requirements.in`。**不要直接编辑 requirements.txt**。
- `requirements-dev.txt`：开发依赖（如 cython、pip-tools）。
- 设置工具同时存在但 `setup.py` 只在打包发行（cythonize `src/**/*.pyx`）时跑。

## 3. 添加新角色（`src/char/<Name>.py`）

走 **`.agent/skills/ok-ww-characters/`**，要点：

1. 继承 `BaseChar`（普通角色）或 `Healer`（治疗位）。
2. **必须**在 `src/char/CharFactory.py` 的 `_char_dict_raw` 中注册：
   ```python
   Labels.char_<name>: {
       'cls': <Name>,
       'res_cd': <共鸣 CD 秒>,
       'echo_cd': <声骸 CD 秒>,
       'liberation_cd': <可选，默认 25>,
       'ring_index': Elements.<元素>,  # 用于协奏环识别
   },
   ```
3. **必须**在 `src/Labels.py` 中有对应的 `char_<name>` 条目（值就是 `coco_annotations.json` 里的 `name`）。
4. `do_perform()` 是主循环；`do_get_switch_priority()` 决定何时被切上场。
5. 用 `time_elapsed_accounting_for_freeze(self.last_xxx)` 而不是 `time.time() - self.last_xxx`，否则解放/入场动画会把 CD 算糊。
6. 优先调封装好的：`click_resonance / click_echo / click_liberation / heavy_attack / continues_normal_attack / heavy_click_forte / is_forte_full / is_con_full`，而不是直接 `send_key`。

## 4. 添加新任务（`src/task/<Name>Task.py`）

走 **`.agent/skills/ok-script-tasks/`**，要点：

1. 选基类：
   - 一次性、要打怪 → `class FooTask(WWOneTimeTask, BaseCombatTask):`
   - 一次性、不打怪 → `class FooTask(WWOneTimeTask, BaseWWTask):`
   - 后台轮询 → `class FooTask(BaseWWTask, TriggerTask):` 或 `class FooTask(BaseCombatTask, TriggerTask):`
2. **必须** `super().__init__(*args, **kwargs)` 在最前。
3. **必须**在 `config.py` 注册到 `onetime_tasks` 或 `trigger_tasks` 里，否则永远不会实例化。
4. `__init__` 里设置 GUI 元数据：`self.name`、`self.description`、`self.icon`、`self.group_name/group_icon`、`self.default_config`、`self.config_description`、`self.config_type`。
5. `default_config` 的 **key 用稳定英文**（持久化到 JSON），中文走 i18n / `config_description`。
6. `TriggerTask` **必须**设 `self.trigger_interval` 与 `self.default_config['_enabled']`。
7. `run()` 内：
   - 用 `self.wait_until / self.wait_ocr / self.wait_click_feature`，不要 raw `time.sleep` 轮询。
   - 用 `self.log_info / log_error / info_set`，不要 print。
   - 用 `self.click_relative(0..1, 0..1)`，**不要写绝对像素**（多分辨率会炸）。
   - 长操作期间适时调 `self.next_frame()` 或 `self.sleep(...)`，否则其它 trigger task 会饿死。

## 5. 视觉特征 / `Labels`

- **不要凭空添加 Labels 枚举值**。如果要识别新东西：
  1. 在 PR/对话中明确告诉用户：要叫 `<feature_name>`，要在 `<file:line>` 用。
  2. 用户在 `ok_templates/` 子模块里用 X-AnyLabeling 标注。
  3. 用户跑 `ok_templates/compress.py`，会自动写入 `assets/images/` + 更新 `assets/coco_annotations.json`。
  4. 用户在 `src/Labels.py` 里加枚举值（值 = `coco_annotations.json` 中的 `name`）。
- 已有 label 但找不到 → 调 `threshold` / 缩 `box=...` / 检查 `frame_processor`，**不要换名字**。

## 6. 国际化（i18n）

- 翻译目录：`i18n/<locale>/LC_MESSAGES/ok.po` → 编译为 `ok.mo`。
- 已存在：`zh_CN`、`zh_TW`、`ja_JP`、`ko_KR`、`es_ES`。`en_US` 不存在 catalog（源语言）。
- 走 **`.agent/skills/ok-script-i18n/`** 的 helper：
  ```powershell
  .\.venv\Scripts\python.exe .agent\skills\ok-script-i18n\scripts\task_i18n_helper.py scan --task src\task\DailyTask.py
  .\.venv\Scripts\python.exe .agent\skills\ok-script-i18n\scripts\task_i18n_helper.py check --i18n i18n
  .\.venv\Scripts\python.exe .agent\skills\ok-script-i18n\scripts\task_i18n_helper.py compile --i18n i18n
  ```
- 翻译什么：`name` / `description` / `default_config` 的字符串值 / `config_description` / `config_type` 选项 / 用户可见 OCR 文本。
- 不翻译什么：`default_config` 的 **key**（持久化字段）、纯日志字符串。

## 7. 测试

- 框架：`unittest` + `ok.test.TaskTestCase`。
- 注入截图：`self.set_image('tests/images/xxx.png')` 或 `self.set_image('ok_templates/xxx.png')`，再断言 `task.in_combat()` / `task.chars[0].name` / etc.
- 跑测试：`run_tests.ps1`（CI 用同样的逻辑）。
- 改了识别/可用性/切人优先级 → **必须**加 / 改对应的 `tests/Test*.py`。
- `tests/images/` 在 `.gitignore` 中（部分），但仓库内有少量入仓的 sample；新加测试图请确认是否需要入仓。

## 8. Git / 提交

- **不要碰**：`.claude/`、`CLAUDE.md`（在 `.gitignore`，是个人设置）。
- **不要 commit**：`configs/`、`logs/`、`screenshots/`、`click_screenshots/`、`__pycache__/`、`*.pyx`、`*.cpp`（cythonize 的产物）、`.venv/`。
- **不要修改** `.gitignore` 里现有的忽略项，除非有充分理由。
- **不要修改** `.gitmodules`（`ok_templates` 是 submodule）。
- Commit 信息：保持简短的英文/中文均可，参照仓库历史风格。
- **不要带** Claude 的 footer / Co-authored-by 行，**除非用户主动要求**。

## 9. 截屏处理器（screenshot_processor）

`config.py` 里全局挂了 `make_bottom_right_black`：每帧把右下角约 13% × 2.5% 区域涂黑。这是为了遮掉小地图旁的坐标文本（会干扰 OCR）。**新加全屏 OCR 范围时记得避开这块区域**或者考虑你的 box 与之是否冲突。

## 10. 多分辨率支持

- `config.supported_resolution`：16:9，min 1280×720，会自动 resize 到 `[(2560,1440), (1920,1080), (1600,900), (1280,720)]` 之一。
- **绝对**用 `self.box_of_screen(x1,y1,x2,y2)` / `self.click_relative(x,y)` / `self.width_of_screen(0..1)`，**绝对禁止**写死像素。
- 模板匹配时按需指定 `target_height=720`（让框架自动 scale 模板到目标高度）。

## 11. 命令行参数

```bash
ok-ww.exe -t 1 -e   # 启动后跑第 1 个 onetime task，完成后退出
```

- `-t N` / `--task N`：onetime_tasks 列表的 1-based 序号。
- `-e` / `--exit`：完成后退出整个进程。

加新 onetime task 时考虑它的位置可能影响用户的脚本调用（如果用户写了 `-t 3` 而你插队到第 2，就会指向错的任务）。

## 12. 与 ok-script 框架的边界

本仓里**禁止**直接调用：
- `cv2.matchTemplate` / 自己写 OCR / 自己写截屏 → 用 `self.find_one / self.ocr / self.frame`。
- `pyautogui` / `pynput` 直接发键 → 用 `self.send_key / self.click / self.click_relative / self.send_key_down/up`。
- `time.sleep` 长时间 → 用 `self.sleep`（含月卡检查）/ `self.wait_until`。
- 直接写 `print` → 用 `self.log_info / log_warning / log_error / log_debug`。

如果框架里没有想要的能力 → 在 `BaseWWTask` / `BaseCombatTask` 里加方法封装，再让具体 task 调用，**不要在 task 里 inline 一堆原始调用**。

## 13. 性能

- `TriggerTask` 的 `trigger_interval` 别低于 0.1（除非真的需要，比如 `AutoCombatTask`）。
- `wait_until(..., time_out=...)` 默认会阻塞，注意别在 0.1s 间隔的 trigger 里写超过 5s 的 timeout。
- `find_one` 比 `ocr` 便宜，能用模板就别用 OCR。
- YOLO（声骸检测）是**最贵**的，仅在 `Pick Echo Config.Use OCR` 开且场景需要时跑。

## 14. 对 AI 助手的额外要求

1. **回答语言匹配用户**：用户中文 → 回中文；用户英文 → 回英文；用户混用 → 关键术语双语。
2. **不要重命名已经入仓的 `Labels` 枚举值** —— 它会破坏 `coco_annotations.json` 与模板图的对应。
3. **不要改 `config.py` 的 task 列表顺序** —— 会影响命令行 `-t N` 的语义。
4. **写代码前先确认** 该改的是 `BaseWWTask` 还是具体 task：通用能力（地图、登录、月卡、F 拾取）放基类；游戏内具体玩法放 task。
5. **写完后** 可选地跑 `tests/`，至少跑改动相关的那些。
6. **不主动**做这些事，除非用户明示：commit、push、改 README、改 CI workflows、改 i18n 译文（用户没要求翻译时）、改 `.gitignore`。
