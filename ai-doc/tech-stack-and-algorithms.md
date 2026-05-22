# Tech Stack & Key Algorithms

> 本篇是 **算法/流程层** 的速读手册。读完 `project-overview.md` 之后再读这里 —— 那篇讲"代码在哪里"，本篇讲"代码在做什么、怎么做的"。

---

## 一、技术栈一览

### 1.1 运行时

| 层 | 选型 | 说明 |
| --- | --- | --- |
| 解释器 | **Python 3.12**（强约束） | `pyappify.yml: requires_python: "3.12"` |
| 自动化框架 | **`ok-script` 1.0.130** | 提供截屏/输入/任务调度/GUI/特征匹配/OCR 抽象，本仓库是其 *app* |
| GUI | **PySide6 6.9.1** + `pyside6-fluent-widgets 1.8.3`（基于 `qfluentwidgets`） | Fluent Design 风格 |
| 打包 | **`pyappify`** + GitHub Actions | 输出 `*-{China,Global}-setup.exe` |
| 国际化 | **gettext** (`.po` → `.mo`) | `i18n/<locale>/LC_MESSAGES/ok.po` |

### 1.2 计算机视觉 / 图像处理

| 用途 | 库 | 备注 |
| --- | --- | --- |
| 图像基础 | **OpenCV-Python 4.12** + **NumPy 2.2** | 颜色空间转换、模板匹配、二值化、形态学、连通域 |
| 截屏 | **Windows Graphics Capture (WGC)** 优先 → **BitBlt** 回退 | 配置：`config.windows.capture_method` |
| OCR | **`onnxocr-ppocrv5`** (PaddleOCR 模型转 ONNX) | `auto_simplify: True` 繁→简自动化；可启用 OpenVINO + NPU |
| 目标检测 | **YOLOv8 (echo.onnx)** | 仅识别声骸；推理后端 ONNX Runtime（DML/CUDA/CPU）或 OpenVINO（OpenVINO/NPU） |
| Shapely / pyclipper | 经由 OCR 库间接依赖 | 文本检测后处理 |

### 1.3 Windows 输入与交互

| 库 | 用途 |
| --- | --- |
| **`pywin32` 311** | `win32api.GetCursorPos / SetCursorPos`、HDR 检测、句柄管理 |
| **PostMessage** (经 ok-script 封装) | **后台输入注入**，不抢前台焦点；`config.windows.interaction: 'PostMessage'` |
| `pydirectinput` | 部分场景的低级键盘事件 |
| `pynput 1.8.2` | 全局热键 / 鼠标钩子 |
| `pycaw` | 自动静音（后台模式时） |
| `comtypes` | DirectShow / pycaw 的依赖 |

### 1.4 检测后端选择

```text
config.ocr.params.use_openvino == True
       │
       ├─ True  → src.OpenVinoYolo8Detect.OpenVinoYolo8Detect   (CPU/NPU 优先)
       └─ False → src.OnnxYolo8Detect.OnnxYolo8Detect           (DirectML > CUDA > CPU)
```

`Globals.yolo_model` 是 **lazy property**（首次 `find_echos()` 时才加载），权重路径：`assets/echo_model/echo.onnx`。

### 1.5 项目自维护工具

| 工具 | 用途 |
| --- | --- |
| `pip-tools` (`pip-compile`) | 把 `requirements.in` 锁成 `requirements.txt` |
| `Cython` | 发行打包时把 `src/**/*.pyx` 编成 C++ 扩展（日常开发用 .py，pyx 在 .gitignore） |
| `X-AnyLabeling` (`pip install x-anylabeling-cvhub`) | 在 `ok_templates/` submodule 里标注模板，跑 `compress.py` 输出到 `assets/` |
| `GitPython` | 内部更新逻辑使用 |

---

## 二、配置驱动的启动流

`OK(config).start()` 按 `config.py` 里的字典逐字段构造系统：

```text
config.py 的 config dict
│
├── windows               ─→ 找窗口 (UnrealWindow / Client-Win64-Shipping.exe) → 决定截屏方式
├── window_size           ─→ 校正窗口尺寸（min 1200×800）
├── supported_resolution  ─→ 把游戏画面 resize 到 [2560×1440 / 1920×1080 / 1600×900 / 1280×720] 之一
├── ocr                   ─→ 实例化 onnxocr (use_openvino / use_npu)
├── template_matching
│     ├── coco_feature_json     → assets/coco_annotations.json 加载所有特征 + 模板图
│     ├── feature_processor     → src/task/process_feature.py 做按 label 的预处理
│     └── default_threshold=0.8 / horizontal/vertical_variance=0.002
├── screenshot_processor  ─→ make_bottom_right_black: 每帧把右下角 13%×2.5% 涂黑（遮坐标文本）
├── my_app                ─→ 实例化 src.globals.Globals（懒加载 YOLO）
├── scene                 ─→ 实例化 src.scene.WWScene
├── global_configs        ─→ 4 个 ConfigOption: Hotkey / Character / Pick Echo / Monthly Card
├── onetime_tasks (×11)   ─→ 一次性任务实例化 + GUI 注册
└── trigger_tasks (×6)    ─→ 后台轮询任务实例化 + 注册
```

GUI 起来后由用户点开始；命令行 `-t N -e` 自动跑第 N 个 onetime task 完成后退出。

---

## 三、视觉识别三条管线（重点）

### 3.1 Pipeline A：模板匹配（**绝大部分识别走这条**）

```text
游戏帧 (BGR ndarray)
   │
   │  optional: frame_processor (convert_bw / binarize_for_matching / convert_dialog_icon / isolate_white_text_to_black)
   ▼
某个 Box (绝对坐标 or 屏幕比例 box_of_screen)
   │
   ├─ self.find_one('<label>', threshold=0.8, box=..., target_height=720)
   ├─ self.find_best_match_in_box(box, [<label1>, <label2>, ...], threshold=0.6)
   └─ self.wait_feature(...)  / self.wait_click_feature(...)
```

- **Label 来源**：`src/Labels.py`（StrEnum）— 值必须等于 `assets/coco_annotations.json` 中某个 `categories[].name`。两边名字不一致 = 永远找不到。
- **多分辨率**：模板按需 `target_height=720` scale；坐标用 `box_of_screen(0..1)` / `box_of_screen_scaled(3840, 2160, x1, y1, x2, y2)`，**禁止写死像素**。
- **预处理函数**（`src/task/BaseWWTask.py` 末尾）：
  - `convert_bw`：≥244 的像素转白，其余转黑。用于带白色文字图标（exit / world_earth_icon）。
  - `binarize_for_matching`：先转灰度，>244 转白，否则黑（mouse_forte / e_forte / purple_target_distance_icon）。
  - `convert_dialog_icon`：210–244 灰白带，专识别对话三点等中等亮度图标。
  - `isolate_white_text_to_black`：把 244–255 白文字反为黑，剩余转白 → 给 OCR 当输入识别 CD 数字。
- **特殊预处理钩子**：`src/task/process_feature.py::process_feature(name, feature)` —— 在加载阶段就为某些 label 改写模板的 `feature.mat`（例如 `illusive_realm_exit` 转黑白后再匹配）。

### 3.2 Pipeline B：OCR（文本）

```text
self.ocr(box=..., match=re_or_str_or_list, frame_processor=..., target_height=...)
self.wait_ocr(x1, y1, x2, y2, match=..., raise_if_not_found=False, settle_time=1)
```

- 引擎：**onnxocr-ppocrv5**（PaddleOCR PP-OCRv5 转 ONNX）。`use_det / use_cls / use_rec` 三阶段。
- `auto_simplify=True` → 繁体输出自动转简体。
- 典型套路（`BaseWWTask.get_stamina`）：
  ```python
  number_re  = re.compile(r'(\d+)')
  stamina_re = re.compile(r'(\d+)/(\d+)')
  boxes = self.wait_ocr(0.49, 0.0, 0.92, 0.10, match=[number_re, stamina_re], ...)
  ```
- **CD 数字识别专用**：先 `frame_processor=isolate_white_text_to_black` 反色再 OCR，正则 `r'\d{1,2}\.\d'`（`BaseCombatTask.refresh_cd`）。

### 3.3 Pipeline C：YOLOv8（**只用于声骸**）

```text
self.find_echos(threshold=0.3)                # BaseWWTask
   ↓
og.my_app.yolo_detect(frame, threshold, label=0)   # globals.Globals.yolo_detect
   ↓
[On|OpenVino]Yolo8Detect.detect(image, threshold, label)
   ├─ _preprocess: BGR→RGB, letterbox 到 640×640, /255 归一化, NCHW
   ├─ session.run / OpenVINO infer
   └─ _postprocess:
        - transpose squeeze 输出
        - 反 padding + 反 letterbox gain 还原原图坐标
        - 阈值过滤 + class 过滤（label=-1 不限）
        - cv2.dnn.NMSBoxes(IoU=0.45) 非极大值抑制
        - 转 ok-script Box 对象
```

返回的 box 上下都被压扁了（`box.y += h/3; box.height = 1`，便于走到声骸正下方就拾取）。

---

## 四、战斗系统的核心算法（这是最复杂的部分）

### 4.1 总循环（`AutoCombatTask.run` / `BaseCombatTask.combat_once`）

```text
TriggerTask 每 0.1s 跑一次 AutoCombatTask.run()
   │
   ├─ scene.in_team(self.in_team_and_world)?  否 → 退出本轮
   │
   ▼
while in_combat():
   │
   ├─ get_current_char().perform()
   │      │
   │      ├─ if need_fast_perform(): do_fast_perform()
   │      └─ else:                   do_perform()       ← ★ 角色独有的连招在这里
   │
   ├─ NotInCombatException → break（退出战斗）
   ├─ CharDeadException     → 上报、break
   └─ CharRevivedException  → 复活成功，重新进战斗循环
```

### 4.2 战斗状态机：`in_combat()` 决策树（`CombatCheck.do_check_in_combat`）

进入态 = `_in_combat=False` 时：

```
has_target() ─┬─ True → load_chars() → _in_combat=True ──→ 进入"战斗中"
              │                       │
              │                       └─ has_lavitator? (edge_levitator 模板)
              │
              └─ False → (Auto Target 开 || 不是 AutoCombatTask)
                           ↓
                          check_health_bar()
                           ├─ 找到红色血条矩形 (find_color_rectangles, BGR 范围 R:174-225 G:55-85 B:55-76)
                           └─ 或 boss 血条 (R:245-255 G:30-185 B:4-75)
                              ↓ True
                         middle_click 锁定 → has_target() 二次确认 → load_chars
```

战斗中 = `_in_combat=True` 时：

```
in_liberation? → True (大招动画跳过整套检测)
       │
       ▼ False
on_combat_check() → False → reset_to_false('on_combat_check failed')
       │
       ▼
has_target() True ─→ 仍在战斗
       │
       ▼ False
target_enemy(wait=True): middle_click 重新锁定，最长 self.target_enemy_time_out=3s
       │
       ├ 锁回了 → 仍在战斗
       └ 锁不回 → reset_to_false('target enemy failed') → NotInCombatException
```

死亡检测：`raise_not_in_combat()` 先 `wait_feature('revive_confirm_hcenter_vcenter', 0.8)` 探弹窗 → 找到 → 走 `revive_action()`（开传送回城血条满）→ 抛 `CharRevivedException`；找不到则抛 `CharDeadException`。

### 4.3 切人优先级算法（`switch_next_char` + `get_switch_priority`）

枚举值：

```python
class Priority(IntEnum):
    MIN              = -999_999_999
    SWITCH_CD        = -1000      # 0.9s 内刚切过，禁止再切（除非 has_intro）
    CURRENT_CHAR     = -100
    BASE_MINUS_1     = -1
    BASE             = 0
    SKILL_AVAILABLE  = 100        # 有任一可用技能时基础加权
    FAST_SWITCH      = 9_999_999_899
    MAX              = 9_999_999_999
```

`do_get_switch_priority(current_char, has_intro, target_low_con)`：

```python
priority = self.priority                                    # 默认 0
if liberation_available(): priority += count_liberation_priority()   # 默认 1
if resonance_available():  priority += count_resonance_priority()    # 默认 10  ← ★ 共鸣最重
if forte_full():           priority += count_forte_priority()        # 默认 0（角色覆写）
if echo_available():       priority += count_echo_priority()         # 默认 1
if priority > 0:           priority += SKILL_AVAILABLE               # +100
priority += count_base_priority()                                    # 角色覆写
```

`get_switch_priority` 包一层 cooldown 检查：

```python
if priority < MAX and time.time() - last_switch_time < 0.9 and not has_intro:
    return SWITCH_CD            # -1000，本轮禁切
return priority
```

`switch_next_char` 选 candidate：

```python
for char in chars:
    if char == current:
        priority = CURRENT_CHAR           # -100，宁可切别人
    else:
        priority = char.get_switch_priority(...)
    
    if target_low_con:                    # 部分队伍策略要把低协奏值角色顶上去吃 con
        switch_to = argmin(char.current_con)
    elif priority == max_priority:        # 同分看 last_perform，越久没动手越优先
        switch_to = argmin(char.last_perform)
    elif priority > max_priority:
        switch_to = char
```

切人执行循环：

- 反复 `send_key(switch_to.index + 1)`（数字键 1/2/3）每 0.1s 一次
- 每次循环 `in_team()` 检测当前 active index 是否变成目标
- 超时 `switch_char_time_out=5s` 抛 `NotInCombatException`
- 切成功后：若 `has_intro` 则把 `time.time() ~ +0.9s` 计入 `freeze_durations`

### 4.4 Freeze 时间补偿（一个非常 specific 的算法）

游戏的大招/入场/卡肉会让屏幕动画暂停但 `time.time()` 不停。如果直接用 `time.time() - last_resonance` 算 CD，会算糊。

```python
def add_freeze_duration(start, duration=-1.0, freeze_time=0.1):
    """ start: 冻结开始时间; duration<0 自动 = now-start;
        freeze_time: 仅当 duration > freeze_time 才记录（去抖）; 
                     特殊值 -100 表示"入场冻结，普通时计算时不扣"
    """

def time_elapsed_accounting_for_freeze(start, intro_motion_freeze=False):
    elapsed = time.time() - start
    for (freeze_start, duration, freeze_time) in self.freeze_durations:
        if start < freeze_start:                    # 该冻结在 start 之后发生
            if intro_motion_freeze and freeze_time == -100: pass  # 关心入场冻结时不扣
            elif freeze_time == -100: continue       # 普通时间核算时跳过入场冻结
            elapsed -= (duration - freeze_time)
    return elapsed
```

`freeze_durations` 自动只保留最近 60 秒的记录。

### 4.5 协奏值检测：连通域 + 完整环判定（`count_rings` 算法）

输入：屏幕中央偏下一块 `box_of_screen_scaled(3840, 2160, 1431, 1942, 1557, 2068)` 的截图。

```text
1. 按角色元素查 con_colors[ring_index]（6 套，对应 spectro/electric/fire/ice/wind/havoc）
2. 在 box 中心画圆环 mask：
     外圈 r2 = h * 0.42261，内圈 r1 = h * 0.35119（用 Decimal 防浮点误差）
3. cv2.inRange(masked, lower, upper) 得到目标颜色二值图
4. cv2.morphologyEx(MORPH_CLOSE, 3×3) 闭运算补缝
5. cv2.connectedComponentsWithStats 找连通域
6. 对每个连通域：
     - bounding_box_area >= min_area (≈ 1500/8.3M * 屏幕面积)
     - cv2.findContours + approxPolyDP(epsilon = 0.05*周长)
     - is_full = isContourConvex && len(approx) >= 4    ← 用"足够多顶点的近凸多边形"代替"封闭圆环"
7. 多个连通域 → 不算满（is_full=False）
8. 与 con_full_size 持久化的最大面积对比 → 得 percent
```

返回 `(area, is_full)`。`is_con_full()` 通过 `area / con_full_size[ring_index]`，>=1 判满。

### 4.6 角色识别 + 工厂注入（`get_char_by_pos`）

```text
对每个队伍位置 box_char_1 / 2 / 3：
   │
   ├─ 旧角色置信度 > 0.92？ 模板匹配旧角色 label，threshold=0.6 → 命中就复用旧实例
   │
   └─ 否：find_best_match_in_box(box, char_names, threshold=0.6)
            └─ char_names = CharFactory.char_dict.keys() （所有 Labels.char_*）
            └─ 命中 → cls(task, index, res_cd, echo_cd, liberation_cd, char_name, confidence, ring_index)
            └─ 未命中：返回上次的角色 / 普通 BaseChar 占位
```

`load_chars` 跑完后把数字键 1/2/3 自动绑定到屏幕右下角 echo/liberation 的标签（`load_hotkey` 走 `set_key`）。

### 4.7 CD 检测：OCR + 反色 + 列裁剪

`refresh_cd()`（每帧懒刷新一次，`scene.cd_refreshed` 控）：

```python
texts = self.ocr(0.81, 0.86, 0.97, 0.93, frame_processor=isolate_white_text_to_black, match=cd_regex)
# cd_regex = r'\d{1,2}\.\d'
for text in texts:
    if text.x < width*0.86: cds['resonance']  = float(text.name)
    elif text.x > width*0.91: cds['liberation']= float(text.name)
    else:                     cds['echo']      = float(text.name)
```

`get_cd(name)` 减去 `time_elapsed_accounting_for_freeze(cds['time'])` 后判断是否 ≤ 0。

### 4.8 大招检测：彩色模板（每元素 6 套）

```python
con_templates       = ['con_spectro', 'con_electric', 'con_fire', 'con_ice', 'con_wind', 'con_havoc']
lib_ready_templates = ['lib_ready_spectro', ...]      # 头像右上"大招就绪"对号
con_full_templates  = ['con_full_spectro', ...]        # "协奏值满"标志
```

`update_lib_portrait_icon()` 给非当前角色按 `ring_index` 在 `lib_mark_char_<i>` box 里查 `lib_ready_<element>`，命中即标记 `_liberation_available=True`。

---

## 五、世界探索算法

### 5.1 走到目标点 (`walk_to_box`)

```text
loop until end_condition() or time_out:
    target = find_function()        ← 用户传入（如 find_treasure_icon, find_echos[0]）
    if target 丢了:
        next_dir = opposite_direction(last_dir)   # 反向找回
    else:
        x, y = target.center()
        x_abs = |x - 屏宽/2|
        # 阶段 1：先把目标横向居中
        centered = centered or x_abs <= 屏宽 * x_threshold(0.04~0.07)
        if not centered:
            next_dir = 'd' if x > 屏宽/2 else 'a'
        # 阶段 2：上下走，直到目标接近屏幕中线偏下
        else:
            center = 0.45/0.5/0.6 取决于 last_dir
            next_dir = 's' if y > 屏高*center else 'w'
    
    # "贴墙加速"：找到 on_the_wall 就 mouse_down 右键加速
    if running and not find('on_the_wall'): mouse_up
    elif next_dir == 'w' and find('on_the_wall'): running = True; mouse_down
```

走声骸专用版 `walk_to_yolo_echo`：每帧重新调 YOLO 找 echo，找不到连续 3s 后退出，每帧调一次 `pick_f()` 试拾取。

### 5.2 拾取 F 提示（`find_f_with_text`）

```text
1. find_one('pick_up_f_hcenter_vcenter', threshold=0.8)
   失败 → None
2. 等 1s 直到 F 图标白色像素占比 > 0.5（避免抓到刚出来还没亮的 F）
3. 若指定了 target_text:
     在 F 右边构造 search_text_box(x_offset=5.2*F.width, y_offset=-0.8*F.height, 高 4.5*F.height)
     OCR 这块区域 → 匹配文字 (如 absorb_echo_text())
     如果文字落在 box 下半 → scroll_relative(0.5, 0.5, 1) 滚动一下再返回
```

### 5.3 角度对齐（`rotate_arrow_and_find` + `get_mini_map_turn_angle`）

确认主角朝向 → 旋转角度计算：

```text
1. arrow_template = 已知 "玩家小箭头" 模板
2. for angle in 0..359:
       rotated = warpAffine(arrow_template.mat, getRotationMatrix2D(center, -angle, 1.0))
       res = find_one(box=arrow_box, template=rotated, threshold=0.01)
       if res.confidence > max_conf: 记录 angle
3. 返回 max_angle 作为玩家朝向
4. get_angle_between(my_angle, target_angle) → [-180, 180] → 决定按 a/d 转多久
```

小地图寻路：先在 `box_minimap` 内 `find_one(feature)` 找传送图标，再 `calculate_angle_clockwise(box_minimap, target)` 算目标方位角，与玩家朝向相减得到要转的角度。

### 5.4 月卡处理（每天 4:00 弹窗）

```python
def set_check_monthly_card(next_day=False):
    next_4am = today.replace(hour=Monthly Card Time)
    if now >= next_4am or next_day:
        next_4am += 1 day
    next_monthly_card_start = (next_4am - 30s).timestamp()

def should_check_monthly_card():
    return 0 < (time.time() - next_monthly_card_start) < 120  # 4:00 前 30s ~ 4:01:30 触发

def sleep(timeout):                        # ★ 关键：覆写了 BaseTask.sleep
    return super().sleep(timeout - check_for_monthly_card())
```

任务里所有 `self.sleep(x)` 都会**自动**在弹窗时间窗口内被中断去处理月卡，不需要每个任务自己写。

---

## 六、任务编排细节

### 6.1 OneTime Task 生命周期

```text
用户点 [Start]
    │
    ▼
WWOneTimeTask.run(self):
    mouse_reset_task = executor.get_task_by_class(MouseResetTask); mouse_reset_task.run()
    if isinstance(executor.interaction, PostMessageInteraction):
        executor.interaction.activate()             # PostMessage 后台输入需要激活
    sleep(0.5)
    │
    ▼
具体子类 run():                       ← e.g. DailyTask
    self._logged_in = False
    self.ensure_main(time_out=180)    # 等到 in_team_and_world() 才往下
    self.go_to_tower()                # 公共锚点：周本入口
    ... 各任务自己的步骤 ...
    self.log_info('Task completed', notify=True)
    │
    ▼
框架自动 disable 此任务（一次性的）
```

### 6.2 Trigger Task 生命周期

```text
框架后台调度器：
   每 trigger_interval 秒 → 已 enabled 的所有 trigger task → run()
                                              │
                                              ├─ truthy 返回 → "本轮已处理"，停止扫其它 trigger
                                              └─ falsy 返回 → 继续扫下一个 trigger task
```

例如 `AutoLoginTask.trigger_interval=5`，`AutoPickTask` 默认间隔，`AutoCombatTask.trigger_interval=0.1`（高频，因为要紧跟战斗）。

`AutoLoginTask.wait_login()` 有限状态机式的处理：依次匹配 OCR 文本 / 模板，按顺序处理 公告 → 同意协议 → 登录按钮 → 开始游戏 → 重启游戏 → 选服窗口。每一步处理完就 return False（让下次再调一遍），从而避免一帧里假设状态序列。

### 6.3 一条龙任务（DailyTask 完整步骤）

```text
1. WWOneTimeTask.run() 公共前置（mouse_reset + activate）
2. ensure_main(180s) 等到主世界
3. go_to_tower() 周本入口锚点
4. 噩梦巢逻辑：
     - 'Auto Farm all Nightmare Nest' True → run_task_by_class(NightmareNestTask)
     - 'Farm Nightmare Nest for Daily Echo' True 且非默认 farm → 仅刷一个声骸
5. open_daily()：F2 打开任务书 → OCR 'X/180' 进度 → 判断是否还需要刷
6. 如果未满：farm_<选项>(daily=True, used_stamina, config)
     - Tacet (TacetTask) / Forgery (ForgeryTask) / Simulation (SimulationTask)
7. claim_daily()：进度 ≥100 时点 0.93,0.88 领宝箱
8. claim_mail() → 邮件
9. claim_battle_pass() → 战令
10. log_info('Task completed', notify=True)
```

`use_stamina(once, must_use)` 的体力规划：

```python
if current >= once*2:                use 双倍 @ x=0.67
elif must_use > once and total >= once*2:  use 双倍（消耗备用波片以保证日常完成）
else:                                use 单倍 @ x=0.32
# 如果点击后弹出 'gem_add_stamina'（用结晶补） → 点确认 → back → 重新点
```

---

## 七、典型场景的端到端流程图

### 7.1 玩家点 [Auto Combat] → 一次完整战斗

```text
用户启用 AutoCombatTask
    │
    ▼ 进入战斗（has_target 或 health_bar 检测到红血条）
load_chars()  ← 模板匹配三个角色头像 → CharFactory 实例化
    │
    ▼ while in_combat()
get_current_char().perform()
    │
    ├─ do_perform()  e.g. Verina:
    │     1. has_intro: sleep 0.8 等动画落地
    │     2. _force_cast_resonance(): 循环按 e 直到 has_cd 或 con_full
    │     3. click_echo()
    │     4. click_liberation()  if 可用
    │     5. _consume_forte_energy(): FFT 分析黄色频率条计算能量段，按段数选不同打法
    │           - 1 段 → heavy_attack(0.6)
    │           - 2-3 段 → jump + 空中连点
    │           - 4 段 → 蓄力滑步 + 空中连点
    │     6. switch_next_char()  ← 走 Priority 系统选下一个角色
    │
    └─ 中途任意时刻：has_target() 丢失 → middle_click 锁回 → 锁不回 → 退出
```

### 7.2 玩家点 [Farm Echo] → 自动刷声骸

```text
FarmEchoTask.run()
    │
    ▼ ensure_main → 锁定刷怪点（地图 / 传送配置）
loop:
   ├─ teleport_to_point()
   ├─ run_to_target()        ← walk_to_box(find_function)
   ├─ AutoCombatTask 接管打怪（trigger 自动 fire）
   ├─ 战斗结束 → run_in_circle_to_find_echo(circle_count=3)
   │      绕圈 w/a/s/d 各 0.8s（每两步加 0.8s），每段调 send_key_and_wait_f → pick_f
   ├─ yolo_find_echo()       ← 中心位 YOLO 推理 → walk_to_yolo_echo
   ├─ pick_echo()            ← find_f_with_text(absorb 文字) → send_key('f') → handle_claim_button
   └─ stat: incr_drop(dropped); Echo per Hour = count / elapsed * 3600
```

### 7.3 玩家被怪打死 → 自动复活

```text
某帧 do_check_in_combat 抛 raise_not_in_combat
    │
    ▼
wait_feature('revive_confirm_hcenter_vcenter', 0.8, 2s)
    │
    ├─ 找到 → revive_action():
    │     send_key('esc') 关弹窗
    │     go_to_tower()                # 周本入口锚点
    │     teleport_to_heal():
    │        send_key('m') 开地图
    │        find_best_match_in_box('map_way_point' / 'map_way_point_big', 0.6)
    │        click → wait_feature('gray_teleport') → click_box(travel)
    │        wait_in_team_and_world(20s)
    │     → CharRevivedException （任务捕获后重新进战斗循环）
    │
    └─ 找不到 → CharDeadException（任务级别上报"角色死亡"）
```

---

## 八、性能与稳定性要点

| 项 | 数值/约束 |
| --- | --- |
| 模板匹配阈值 | 默认 0.8（`config.template_matching.default_threshold`） |
| 模板匹配位置容差 | 0.002（×屏宽/屏高） |
| YOLO 输入 | 640×640，IoU=0.45，NMS 在 OpenCV |
| OCR 后端 | onnxocr-ppocrv5 + 可选 OpenVINO + 可选 NPU |
| `AutoCombatTask` 频率 | 0.1s/次 |
| `AutoLoginTask` 频率 | 5s/次 |
| `MouseResetTask` 频率 | 10s/次（鼠标移动 >200px 且接近中心 → 拽回） |
| 切人 cooldown | 0.9s（防鬼畜） |
| 切人最大等待 | 5s（`switch_char_time_out`） |
| 进战等待 | `wait_combat_time=200s`（`combat_once`） |
| Freeze 记录窗口 | 60s（仅保留 `time.time()-60` 后的） |
| 月卡触发窗口 | 配置时间前 30s ~ 后 90s（共 120s） |
| 启动超时 | 120s（`config.start_timeout`） |
| 截屏处理 | 每帧把右下角 13%×2.5% 涂黑（去坐标干扰） |

### 失败重试模式（项目里反复出现）

1. **二次确认型**：`has_target(double_check=False)` → 找不到 → `send_key('esc')` 关掉 echo 轮盘 → 重试。
2. **post_action 型**：`wait_until(condition, post_action=lambda: self.click_relative(0.5, 0.89))`，等待中持续戳坐标推动状态。
3. **重新锁定型**：`target_enemy()` 中点中键最多 3s。
4. **Reset & Re-enter 型**：战斗丢失 → `reset_to_false()` 清状态 → 抛 `NotInCombatException` → 任务捕获后再调 `combat_once`。

---

## 九、扩展时的算法复用清单

加新功能前先看你**是否已经有现成方法**（避免重新发明轮子）。

### 视觉/识别

- 找一个 UI 元素 → `self.find_one(label, threshold, box, frame_processor)`
- 在多个候选里找最像的 → `self.find_best_match_in_box(box, [labels], threshold)`
- 等待元素出现 → `self.wait_feature(label, time_out, threshold)`
- 等待并点击 → `self.wait_click_feature(label, ...)`
- 找文本 → `self.ocr(box, match=re_or_str)` / `self.wait_ocr(...)`
- 找声骸 → `self.find_echos(threshold)`（封装了 YOLO）
- 找彩色矩形（血条等） → `find_color_rectangles(frame, color_range, min_w, min_h)`
- 计算颜色占比 → `self.calculate_color_percentage(color_range, box)`

### 移动/输入

- 走到屏上某图标 → `self.walk_to_box(find_function, end_condition, x_threshold, y_offset)`
- 走到声骸 → `self.walk_to_yolo_echo(...)`
- 朝某方向走直到出现 F → `self.send_key_and_wait_f(direction, time_out, target_text)`
- 转向某角度 → `self.get_my_angle()` + `self.get_angle_between()` + `self.turn_direction()`
- 居中相机 → `self.center_camera()` (中键)
- 点击屏幕比例 → `self.click_relative(x, y, after_sleep)`
- 模拟按键 → `self.send_key(key, after_sleep)`、`send_key_down/up`
- 滚动 → `self.scroll_relative(x, y, dy)`

### 战斗/技能

- 释放共鸣 → `self.click_resonance(post_sleep, has_animation, send_click)`
- 释放声骸 → `self.click_echo(duration, sleep_time, time_out)`
- 释放大招 → `self.click_liberation(con_less_than, send_click, wait_if_cd_ready)`
- 重击 → `self.heavy_attack(duration)`
- 持续平A → `self.continues_normal_attack(duration, interval, until_con_full)`
- 检查可用 → `self.available(name, check_color, check_cd)` / `self.has_cd(name)`
- 检查协奏满 → `self.is_con_full()` / `self.get_current_con()`
- 检查共鸣回路 → `self.is_forte_full()` / `self.is_e_forte_full()` / `self.is_mouse_forte_full()`
- 切下一角色 → `self.switch_next_char(post_action, free_intro, target_low_con)`
- 解放 freeze 修正 → `self.time_elapsed_accounting_for_freeze(start)` + `self.add_freeze_duration(start, dur)`

### 流程控制

- 等到主世界 → `self.ensure_main(esc=True, time_out=30)`
- 在队伍中 → `self.in_team()` 返回 `(in_team, current_index, char_count)`
- 检查/处理月卡 → `self.set_check_monthly_card()` + `self.check_for_monthly_card()`
- 跑一次完整战斗 → `BaseCombatTask.combat_once(wait_combat_time, raise_if_not_found)`
- 复活 → `self.revive_action()` / `self.teleport_to_heal()`
- 打开 F2 书 → `self.openF2Book(feature='gray_book_quest')`
- 点确认 → `self.click_confirm(timeout)`
- 用一次体力 → `self.use_stamina(once, must_use)` 返回 `(can_continue, used)`

---

## 十、看完之后建议立即跑一遍测试

```powershell
.\.venv\Scripts\python.exe -m unittest tests/TestChar.py     # 角色识别 + CD 检测
.\.venv\Scripts\python.exe -m unittest tests/TestCD.py       # CD 数字 OCR
.\.venv\Scripts\python.exe -m unittest tests/TestCon.py      # 协奏值环检测
.\.venv\Scripts\python.exe -m unittest tests/TestCombatCheck.py  # 战斗状态机
.\.venv\Scripts\python.exe -m unittest tests/TestEcho.py     # YOLO 声骸检测
.\.venv\Scripts\python.exe -m unittest tests/TestOCR.py      # OCR 整体
.\.venv\Scripts\python.exe -m unittest tests/TestMap.py      # 地图导航
```

每个 Test 都通过 `self.set_image('xxx.png')` 注入截图来 deterministic 验证算法。读懂任意一个 Test 就能搞清这个模块跑通的样子是什么。
