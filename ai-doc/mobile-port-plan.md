# Mobile Port Plan -- 让 ok-ww 跑在 MuMu 12 上

> **状态**：阶段 0 ✅ ｜ 阶段 1 ✅（含一次重写）｜ 阶段 2 待用户填 key_map ｜ 阶段 3 待实战
> **作用**：架构决策记录（ADR）+ 实施计划。下次会话或换 AI 接手时**先读这一篇**。

---

## 0. 重大调整记录（2026-05）

### 0.1 把"自己造 ADB / minitouch / hwnd 探测"删了

**起因**：阶段 1 第一版骨架自己写了 `adb_helper.py`、`input_backends.py`（AdbShell + Minitouch）、`windows_config.py`（hwnd_class 模式）。

**问题**：用户提示我"你可以从 git 仓库拉取，而不是猜测"。读了一遍 ok-script 源码后发现：

- `ok/device/DeviceManager.py` 已经有完整 ADB 模式 (`config['adb']`)
- `ok/device/capture_methods/nemu_ipc.py` -- NEMU IPC 直读 MuMu 显存（**最小化也能跑**，~30 fps）
- `ok/device/capture_methods/adb.py` -- exec-out screencap 备用（~3 fps，万能）
- `ok/device/interaction_methods/adb.py::ADBInteraction` -- 已经实现 click(NEMU IPC click_nemu_ipc) / swipe (swipe_nemu / swipe_u2 / `input swipe`) / send_key（KEYCODE_*）
- `ok/alas/emulator_windows.py::EmulatorManager` -- 自动从注册表发现 MuMu/雷电/夜神 + player_id

**结论**：原来插件 70% 是在重新发明轮子。**全部重写**：

| 删除 | 因为 ok-script 已经有 |
| --- | --- |
| `adb_helper.py` | `DeviceManager.adb` + `adb_connect` + `shell` |
| `input_backends.py` (AdbShell / Minitouch) | `ADBInteraction.click/swipe`，根据 capture method 自动选 NEMU IPC / u2 / `input` |
| `input_adapter.py` | 合并进 `task_wrapper.MobileInputMixin`（瘦身 ~250 行） |
| `windows_config.py` | ADB 模式不需要 hwnd（NEMU IPC 通过 player_id 直接 attach 到 MuMu VM） |
| `Mobile Config` 里的 `ADB Port` / `Input Backend` 选项 | EmulatorManager 自动发现端口；ADBInteraction 自动选最佳 swipe 实现 |

### 0.2 由此带来的副作用：用户最初的两个顾虑都解决了

- **顾虑 A**：MuMu 最小化时 WGC 抓不到稳定画面 → ✅ NEMU IPC 直接读显存，与窗口可见性无关
- **顾虑 B**："既然走 ADB，为啥还要选窗口" → ✅ 现在不选了，ADB 模式没有 hwnd 概念

---

## 1. 背景与目标

### 1.1 用户需求
让现在只支持 PC 端鸣潮的 `ok-ww`，**额外**支持手游版鸣潮在 MuMu 12 模拟器里运行。

### 1.2 用户约束（重要 -- 决定了所有架构选择）

| # | 约束 | 影响 |
| --- | --- | --- |
| 1 | PC 键盘操作在手游里都有触屏对应物 | 输入语义可一对一映射 |
| 2 | 具体映射等用户后续提供 | key_map.py 全部 TODO |
| 3 | 只支持 MuMu 12，其他模拟器以后再说 | 只做一个 plugin，不做抽象多模拟器层 |
| 4 | 分辨率/坐标先等比转换，留可视化调试 | 优先 MobileDiagnosisTask |
| 5 | 视觉资产先复用 PC 端，效果不好再说 | 不动 `assets/`、不动 YOLO 模型 |
| 6 | 模拟器支持必须**可插拔、对原代码减少入侵** | 走 `plugins/` 目录 + Mixin 注入，src/ 一行不改 |
| 7 | minitouch 与 adb shell input **两个 backend 都要** | 重写后不再相关 -- ok-script 内部已包含两套 + NEMU IPC（更快） |

### 1.3 不做的事（明确划线）

- ❌ 不抽象多模拟器层（雷电/夜神/BlueStacks 以后再扩）
- ❌ 不重抓视觉资产（先复用 PC 模板）
- ❌ 不修改 `src/`（这是硬约束）
- ❌ 不修改 `main.py` / `main_debug.py` / `config.py`
- ❌ 不修改 `assets/`、`ok_templates/`（视觉资产）
- ❌ 不重训 YOLO 模型（先复用，效果差再说）
- ❌ 不修改 ok-script 自身（只用其公开 API + 注入到 task class MRO）

---

## 2. 阶段 0 验证记录（已完成 ✅）

| 验证 | 命令 | 结果 |
| --- | --- | --- |
| ADB 能连 MuMu 12 | `adb connect 127.0.0.1:16384` | ✅ connected |
| ADB 能模拟点击 | `adb -s 127.0.0.1:16384 shell input tap 500 500` | ✅ 手游里有反应 |
| 多设备冲突 | `adb shell input ...` 报 "more than one device" | ✅ 用 `-s 127.0.0.1:16384` 显式指定即可（ok-script 内部已经这样做） |

**关键结论**：ADB 链路完全可行。后来发现 ok-script 还有 NEMU IPC 直驱 MuMu 显存的能力，更快、可后台。

---

## 3. 架构（重写后版本）

### 3.1 总览

```
┌──────────────────────────────────────────────────────────────────┐
│  src/task/*.py、src/char/*.py（一行不改）                         │
│  调 self.send_key('e') / self.click_relative(x, y) 等             │
└────────────────────┬─────────────────────────────────────────────┘
                     │ MRO 拦截
                     ▼
        ┌────────────────────────────────────────────────┐
        │  MobileInputMixin (plugins/mumu12/task_wrapper) │
        │   - send_key('e') → 查 key_map → click_relative │
        │   - send_key_down/up('w') → 摇杆状态机 → swipe   │
        └────────────┬───────────────────────────────────┘
                     │ self.click_relative / self.swipe_relative
                     ▼
        ┌────────────────────────────┐
        │  ok-script BaseTask         │
        │   - click_relative/swipe_*  │
        └────────────┬───────────────┘
                     │ self.executor.interaction
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│  ok-script ADBInteraction (ok/device/interaction_methods/adb.py) │
│   click   → 若 capture 是 NemuIpc → nemu_impl.click_nemu_ipc     │
│           → 否则                  → device.shell('input tap')    │
│   swipe   → 若 NemuIpc → swipe_nemu (down/move/up via NEMU IPC)  │
│           → 若 u2 可用 → swipe_u2  (uiautomator2 touch.down/...) │
│           → 否则       → device.shell('input swipe ...')         │
│   send_key → device.shell('input keyevent KEYCODE_*')           │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
                MuMu 12 (Android)
                     ↑
                     │ 截屏路径独立：
        ┌────────────┴─────────────┐
        │  capture_method（ok-script 自己选）  │
        │   - NemuIpcCaptureMethod （~30fps，最小化也能跑）│
        │   - ADBCaptureMethod      （~3fps，screencap）  │
        └─────────────────────────────────────────────────┘
```

### 3.2 决策 A：插件目录 + 字符串路径重写（零入侵的关键）

ok-script 通过**字符串**懒加载 task 类：

```python
# config.py
'onetime_tasks': [
    ["src.task.DailyTask", "DailyTask"],   # ← 字符串路径
    ...
]
```

**利用这一点**：plugin 启动时把这些字符串改写为指向 plugin 内的"包装类"，这样 `src/` 一行不改。

```
原始：["src.task.DailyTask",        "DailyTask"]
重写：["plugins.mumu12.tasks", "MobileDailyTask"]
                                       ↑
                            动态生成的子类
                            type('MobileDailyTask',
                                 (MobileInputMixin, DailyTask),
                                 {})
```

`MobileInputMixin` 在 MRO 前面，覆盖 `send_key / send_key_down/up / middle_click / mouse_down/up`。`DailyTask` 内部的 `self.send_key('e')` 透明走 mixin → key_map → ok-script 的 `click_relative`。

### 3.3 决策 B：保留 PC 配置完全不动 + ADB 模式独立选

`apply_to(config)` 在原 config 深拷贝上：

1. `pop('windows')` -- 移除 PC 窗口配置
2. 添加 `config['adb'] = {'capture_method': ['ipc', 'adb'], 'interaction': 'ADB', 'packages': [...]}`
3. wrap 所有 task entry
4. append plugin 自己的几个 OneTime / Trigger task（calibration, diagnosis）

ok-script 的 `DeviceManager.__init__` 只看到 `config['adb']`，自动走 `EmulatorManager` 路径（注册表发现 MuMu）→ `adb_connect` → 选 capture method → 用 `ADBInteraction`。

### 3.4 决策 C：摇杆通过短 swipe pump 模拟

ok-script 没有"摇杆持续按住"的高层 API。`MobileInputMixin._pump_joystick` 每次推算合成方向 + 调用 `self.swipe_relative(center, target, duration=0.3)`。连续按 `w` = 每 ~300ms pump 一次，character 就持续向前走。

实战受限：方向切换瞬间会有 swipe 尾巴。如果不够 smooth，要切到直驱 NEMU IPC 的 down/move/up 三件套（`ADBInteraction.swipe_nemu` 已经有，但需要绕过 BaseTask.swipe_relative 的封装）。

---

## 4. 文件清单（重写后）

```
plugins/mumu12/
├── __init__.py               # apply_to(config) -- 唯一公共入口
├── README.md                 # 插件自述
├── mobile_config.py          # GUI 选项（包名 / 诊断开关）
├── key_map.py                # ★ 全部 TODO，等用户填坐标
├── task_wrapper.py           # MobileInputMixin + wrap_task_entry()
├── tasks/                    # 动态包装类的命名空间
│   └── __init__.py           # 启动时被 setattr 填充
├── diagnosis_task.py         # MobileDiagnosisTask（可视化叠加）
├── calibration_tasks.py      # AdbProbe / TapTest / SwipeTest
└── probe.py                  # 命令行 bootstrap：列 MuMu 进程 + ADB 设备 + WuWa 包名

main_mobile.py                # 新入口（5 行）
ai-doc/mobile-port-plan.md    # 本文档
build.bat                     # 一键 build / portable 打包
```

**新增文件总计：10 个**（少于第一版的 12 个，因为合并了 input_adapter，删了 adb_helper / input_backends / windows_config）。**修改的旧文件：0 个**。

---

## 5. 关键技术点

### 5.1 Mixin 注入机制（task_wrapper.py 的核心）

```python
class MobileInputMixin:
    """所有 mobile 版 task 多继承的第一个父类"""

    def send_key(self, key, *a, **kw):
        key = self._norm_key(key)
        if key in _DIR_VECTORS:           # w/a/s/d 走摇杆
            self.send_key_down(key); time.sleep(0.10); self.send_key_up(key)
            return True
        return self._tap_mapped(key)      # 其他键查 key_map.py

    def _tap_mapped(self, key):
        from .key_map import lookup
        point = lookup(key)
        if point is None:
            logger.warning("[mobile-key-map TODO] key=%r", key)
            return False
        self.click_relative(point.rel_x, point.rel_y)
        return True

    def send_key_down(self, key, *a, **kw):
        ...  # 加进 _joystick_dirs，调 _pump_joystick

    def send_key_up(self, key, *a, **kw):
        ...  # 从 _joystick_dirs 移除，重新 pump
```

`wrap_task_entry`：

```python
def wrap_task_entry(entry):
    """[module_path, class_name] → [plugins.mumu12.tasks, Mobile<Name>]"""
    module_path, class_name = entry
    if module_path.startswith('plugins.mumu12.'):
        return [module_path, class_name]              # plugin 自己的 task 不包
    if (module_path, class_name) in DISABLED_ON_MOBILE:
        return ['plugins.mumu12.tasks', _ensure_disabled_stub(class_name)]
    return ['plugins.mumu12.tasks', _ensure_wrapped(module_path, class_name)]

def _ensure_wrapped(module_path, class_name):
    wrapped_name = f'Mobile{class_name}'
    if not hasattr(_mobile_tasks_namespace, wrapped_name):
        original_cls = getattr(importlib.import_module(module_path), class_name)
        wrapped = type(wrapped_name, (MobileInputMixin, original_cls), {...})
        setattr(_mobile_tasks_namespace, wrapped_name, wrapped)
    return wrapped_name
```

### 5.2 摇杆状态机（合并进 MobileInputMixin）

PC 端的 `send_key_down('w'); sleep(2); send_key_up('w')` 在手游里要变成"按住摇杆向上 2 秒"。多个方向键同时按时（如 `w + a` = 左上）摇杆位置要重算。

```python
_DIR_VECTORS = {'w': (0, -1), 'a': (-1, 0), 's': (0, 1), 'd': (1, 0)}

class MobileInputMixin:
    def _pump_joystick(self):
        if not self._joystick_dirs:
            return
        # 合成方向：累加 + 归一化
        dx = sum(_DIR_VECTORS[d][0] for d in self._joystick_dirs)
        dy = sum(_DIR_VECTORS[d][1] for d in self._joystick_dirs)
        norm = math.hypot(dx, dy) or 1.0
        ux, uy = dx / norm, dy / norm
        target_rel_x = JOYSTICK.center_x + ux * JOYSTICK.radius
        target_rel_y = JOYSTICK.center_y + uy * JOYSTICK.radius
        self.swipe_relative(JOYSTICK.center_x, JOYSTICK.center_y,
                            target_rel_x, target_rel_y, duration=0.3)
```

> ⚠️ swipe 模拟的"按住"会有 ~300ms 尾巴，方向切换时不绝对干净。如果实战不够顺，下一步切到直驱 `ADBInteraction.swipe_nemu` 的 down/move/up 三件套（NEMU IPC 真 multi-touch）。

### 5.3 不需要再做的事

- ❌ 自己写 `adb_helper.py`：`og.device_manager.shell()` 直接用
- ❌ 自己写 `input_backends.py`：`ADBInteraction` 已经按 capture method 选最佳 swipe 实现
- ❌ 自己写 `windows_config.py`：`EmulatorManager` 注册表发现 MuMu 安装位置 + player_id
- ❌ 显式跑 `wm size` 算坐标：`BaseTask.click_relative` 用当前 capture frame 的尺寸自动转换

---

## 6. 实施阶段拆分

### ✅ 阶段 0：可行性 spike（已完成）
- [x] ADB connect MuMu 12
- [x] adb shell input tap 有反应
- [x] 确认坐标系是 Android 系统坐标
- [x] 确认 multi-touch 必须走 minitouch 或 NEMU IPC

### ✅ 阶段 1：plugin 骨架（已完成 + 一次重写）

第一版（已弃）：自己写 adb_helper / input_backends / minitouch / hwnd_class。

第二版（当前）：基于 ok-script ADB 模式重写。

**当前文件状态**：
- ✅ `__init__.py` -- apply_to(config) 替换 windows → adb，wrap tasks，注册 GUI 选项
- ✅ `mobile_config.py` -- Game Package Names + Show Diagnosis Overlay
- ✅ `task_wrapper.py` -- MobileInputMixin（含摇杆）+ wrap_task_entry
- ✅ `key_map.py` -- 全部 TODO（用户阶段 2 填）
- ✅ `tasks/__init__.py` -- 动态挂载点
- ✅ `diagnosis_task.py` -- 叠加层 + capture/interaction 类型展示
- ✅ `calibration_tasks.py` -- AdbProbe / TapTest / SwipeTest
- ✅ `probe.py` -- 命令行：MuMu 进程 + ADB 设备 + WuWa 包名
- ✅ `main_mobile.py` -- 5 行入口

**阶段 1 验收标准**：
- 跑 `python main_mobile.py` GUI 能开
- GUI 上能看到原有所有 task + 多一个 `MobileDiagnosisTask` + 3 个校准 task
- 任何调用 `send_key` 的操作打印 `[mobile-key-map TODO] key='e'` 但不崩溃
- `python main.py` 运行行为完全不变
- `python -m plugins.mumu12.probe` 能列出 MuMu 进程 + ADB 设备 + 包名

### 🟡 阶段 2：填映射 + 单点验证（用户给坐标后）

**用 GUI 里的校准工具**（plugin 装好后会自动出现在 GUI 的 **Mobile** group 下）：

| 工具 | 干啥 |
| --- | --- |
| `Probe ADB Connection` | 跑 `wm size`、`getprop`、`pm list packages`，验证 ADB 链路 + Android 信息 + 真 WuWa 包名 |
| `Tap Test` | 输入 `(rel_x, rel_y)`，跑 N 次 tap。**反复试以找出每个按钮的坐标** |
| `Swipe Test` | 输入起止相对坐标 + 时长，**校准摇杆中心 + 半径** |
| `Mobile Diagnosis Overlay` | TriggerTask，把 PC 模板的所有 box 叠加到 MuMu 画面上看是否对位 |

填好 `key_map.py`（直接编辑文件 / 把校准任务输出的代码片段复制粘贴），验证：
- 单点能点中目标（如打开 F2 书）
- send_key('w') 角色能动几步

### 🟢 阶段 3：实战调优

1. 跑 `AutoCombatTask` 测一段战斗
2. 跑 `DailyTask` 测一条龙
3. 视觉识别失准的 box 用 MobileDiagnosisTask 找出来
4. 摇杆走位不顺则切到直驱 NEMU IPC down/move/up
5. 如果 PC 模板在手游 UI 上识别率太差 → 决定是否补抓 mobile 版本模板（违反约束 5 之前先确认）

---

## 7. 用户接口（你需要做什么）

### 7.1 切换平台

```bash
# PC 鸣潮（不变）
python main.py

# MuMu 12 手游
python main_mobile.py
```

### 7.2 删除 mobile 支持回到原状

```bash
rm -rf plugins/mumu12 main_mobile.py
# 项目 100% 回到原状
```

### 7.3 配置项（GUI / Settings / Mobile Config）

| 配置项 | 默认 | 说明 |
| --- | --- | --- |
| Game Package Names | `com.kurogame.wutheringwaves,...` | WuWa Android 包名候选；ok-script 按顺序试 |
| Show Diagnosis Overlay | False | 启用 MobileDiagnosisTask 在 GUI 叠加识别框 |

> 不再有 `ADB Port` / `Input Backend` -- ok-script 自己处理了。

---

## 8. 已知风险与应对

| 风险 | 概率 | 影响 | 应对 |
| --- | --- | --- | --- |
| 视觉资产识别率低（PC 模板 ≠ 手游 UI） | 高 | 任务跑不下去 | MobileDiagnosisTask 可视化定位差异，必要时补抓 mobile 模板 |
| key_map 坐标对不准 | 高 | 点击落空 | TapTest 工具迭代调整 |
| 摇杆 swipe 模拟尾巴影响走位 | 中 | 移动卡顿 / 切向不干净 | 切到直驱 NEMU IPC down/move/up |
| EmulatorManager 找不到 MuMu | 低 | ok-script 启动报无设备 | 手动 `adb connect 127.0.0.1:16384`；若 MuMu 未安装到默认位置则需补到注册表 |
| `MouseResetTask`（PC 反鼠标抢占）在 MuMu 模式无意义 | 低 | 误触 | 已 disable：`task_wrapper.DISABLED_ON_MOBILE` |
| 月卡处理逻辑（4:00 弹窗）在手游版位置不同 | 中 | 弹窗卡死 | 用 PC 模板能否识别，不行再调 |
| 战斗 CD 数字位置不同 | 高 | CD 检测失效 | 同上，diagnosis 看到位置不对就调 box_of_screen |

---

## 9. FAQ

**Q：为什么不直接 fork 一个 ok-ww-mobile？**
A：fork 后跟随上游主仓更新成本高（每次合并都要解冲突）。plugin 模式让 src/ 不动，上游怎么变都不影响 plugin。

**Q：为什么不用 ok-script 的自定义 interaction（比如自己实现 BaseInteraction）？**
A：用了。`config['adb']['interaction'] = 'ADB'` 直接拿 ok-script 现成的 `ADBInteraction`，不需要自己实现。这一点是阶段 1 第二版才发现的（一开始绕了远路）。

**Q：MobileInputMixin 覆盖了 send_key，但 BaseChar 调用的是 self.task.send_key -- mixin 能拦到吗？**
A：能。`self.task` 是 wrapped 之后的 `MobileXxxTask` 实例，方法解析仍按 MRO 走，先匹配 `MobileInputMixin.send_key`。

**Q：为什么不重抓视觉资产？工作量大不大？**
A：用户约束 5 明确"先复用，效果不好再说"。PC 模板有些图标可能在手游 UI 里也长得一样（共鸣冷却数字、解放就绪对号等通用 UI 素材），先看实际识别率。

**Q：MuMu 12 的 ADB 端口可能变吗？**
A：会，多开实例时端口会递增（16384 → 16386 → 16388）。但 ok-script 的 `EmulatorManager` 通过注册表 + player_id 自动算出来，所以**不需要在 GUI 里手动填端口**。

**Q：截屏是不是仍走 PC 窗口的 WGC？最小化能用吗？**
A：第二版起 NemuIpcCaptureMethod 直读 MuMu 显存，**与窗口可见性无关**，最小化也能 ~30 fps。失败回退到 ADBCaptureMethod（exec-out screencap，~3fps，万能）。

**Q：multi-touch（边走边放技能）现在能做到吗？**
A：能。ADBInteraction.swipe_nemu 直接走 NEMU IPC 的 down/move/up，是真 multi-touch。当前 MobileInputMixin 用的是高层 swipe API（短 swipe pump），如果实战不够好再切到直驱版本。

---

## 10. 当前状态

- ✅ 阶段 0 通过
- ✅ 阶段 1 完成（含一次架构重写）
- 🟡 阶段 2 待用户提供 key_map 数据 + 跑校准 task
- ⬜ 阶段 3 待 key_map 填好后实战

下次接手的 AI / 自己重新开会话时，从"阶段 2 待用户填 key_map" + 当前 task 列表（`TaskList`）继续即可。
