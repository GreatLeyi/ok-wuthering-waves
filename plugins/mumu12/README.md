# ok-ww plugin: MuMu 12 mobile support

让 `ok-ww` 在 **MuMu Player 12** 模拟器里跑 **手游版鸣潮**，对原代码零入侵。

> 完整架构与决策记录：[`ai-doc/mobile-port-plan.md`](../../ai-doc/mobile-port-plan.md)

## 启用 / 关闭

```bash
# 启用 — 用 mobile 入口
python main_mobile.py

# 关闭 / 回到原 PC 模式 — 用原入口
python main.py
```

**完全卸载**（项目恢复出厂）：

```bash
rm -rf plugins/mumu12 main_mobile.py
```

`src/`、`config.py`、`main.py`、`main_debug.py`、`assets/`、`ok_templates/` 等**一行不改**。

## 架构（重写版）

旧版本自己起 ADB / 写 minitouch / 抓 MuMu 窗口 hwnd —— 后来发现 **ok-script 自己已经全有了**，本插件只剩两件事：

1. **告诉 ok-script 用 ADB 模式**（而不是 PC 窗口模式），通过把 `config['windows']` 替换成 `config['adb']`。
2. **把 PC 键盘语义翻译成屏幕坐标**，因为 PC task 代码里写的是 `self.send_key('e')`，而手游里那是屏幕右下的按钮。

ok-script ADB 模式自带能力（无需重新发明）：

| 能力 | 实现 | 文件 |
| --- | --- | --- |
| ADB 连接 + 设备发现 | `DeviceManager` + `EmulatorManager` | `ok/device/DeviceManager.py`, `ok/alas/emulator_windows.py` |
| 截屏（NEMU IPC，~30fps，最小化也能用） | `NemuIpcCaptureMethod` | `ok/device/capture_methods/nemu_ipc.py` |
| 截屏 fallback（ADB exec-out screencap） | `ADBCaptureMethod` | `ok/device/capture_methods/adb.py` |
| 输入（`input tap` / `input swipe` / NEMU IPC click / uiautomator2） | `ADBInteraction` | `ok/device/interaction_methods/adb.py` |

## 文件清单

| 文件 | 作用 |
| --- | --- |
| `__init__.py` | 暴露 `apply_to(config)` —— 唯一公共入口；把 `config['windows']` 换成 `config['adb']`，wrap 所有 task，注册 GUI 选项与校准任务 |
| `mobile_config.py` | 注册 `Mobile Config`（GUI 选项 → Settings）：游戏包名列表、是否显示诊断叠加层 |
| `key_map.py` | **TODO 文件**，等用户填手游里每个按钮的相对坐标 |
| `task_wrapper.py` | `MobileInputMixin` + `wrap_task_entry()` 动态生成子类，瘦身后 ~250 行（合并了原 input_adapter） |
| `tasks/__init__.py` | 动态包装类挂载点（启动时被 `setattr` 填充） |
| `diagnosis_task.py` | `MobileDiagnosisTask`：可视化所有关键 UI box，输出 capture/interaction 类型 |
| `calibration_tasks.py` | **GUI 校准工具**：3 个 OneTime task（AdbProbe / TapTest / SwipeTest）—— 直接用 ok-script 的 `og.device_manager` + `BaseTask.click_relative` / `swipe_relative` |
| `probe.py` | **命令行 bootstrap**：不依赖 ok-script，直接 `python -m plugins.mumu12.probe` 列出 MuMu 进程 + ADB 设备 + 设备上的鸣潮包名 |

## 输入路径

```
Task.do_perform() → self.send_key('e')
        ↓ MRO（动态生成的 MobileXxxTask）
MobileInputMixin.send_key
        ↓ key_map.lookup('e') → ScreenPoint(rel_x, rel_y)
self.click_relative(rel_x, rel_y)         # BaseTask
        ↓
ADBInteraction.click(x_px, y_px)          # ok-script
        ↓ 取决于当前 capture_method
NemuIpc.click_nemu_ipc(x, y)  或  shell('input tap x y')
        ↓
MuMu 12 → Android
```

截屏路径：

```
TaskExecutor → DeviceManager.capture_method.do_get_frame()
        ↓
NemuIpcCaptureMethod  ←—— 优先；最小化也能跑；~30fps
  └─ fallback ↓
ADBCaptureMethod      ←—— 任意场景；exec-out screencap；~3fps
```

## 用户必须提供的内容

`key_map.py` 里所有 `None` 都是 **TODO**：

| 项目 | 例子 | 说明 |
| --- | --- | --- |
| `KEY_MAP['e']` | `ScreenPoint(rel_x=0.93, rel_y=0.85, name='resonance')` | 共鸣技能按钮在屏幕上的相对位置 |
| `KEY_MAP['r']` | `ScreenPoint(0.83, 0.85, 'liberation')` | 共鸣解放 |
| `KEY_MAP['q']` | `ScreenPoint(0.97, 0.62, 'echo')` | 声骸技能 |
| ... 其它技能按钮 | 同上 | 见 `key_map.py` 注释 |
| `JOYSTICK` | `JoystickConfig(center_x=0.18, center_y=0.78, radius=0.10)` | 摇杆中心 + 推杆半径 |

**怎么找坐标**：用 GUI 里 **Mobile** group 下的 3 个校准任务（见下一节"GUI 内置工具"），不要手算。

## GUI 内置工具（Mobile group）

启用 plugin 后 GUI 的任务列表会出现一个 **Mobile** 分组，包含 4 个工具：

### 一次性任务（OneTime）

| 工具 | 用途 | 配置 |
| --- | --- | --- |
| **Probe ADB Connection** | 跑 `wm size` / `getprop` / `pm list packages`，输出 Android 版本、分辨率、设备型号、当前 capture method 类型，并自动在已安装包里搜索 wuther/kuro/kurogame 关键字定位鸣潮真实包名 | 无 |
| **Tap Test (find button coords)** | 在指定相对坐标 `(rel_x, rel_y)` 上 tap N 次（默认 3 次，间隔 1 秒）。**用来反复试找按钮位置** —— 估个值 → 跑一下看哪个按钮亮 → 微调 → 再跑 | `Relative X` `Relative Y` `Tap Count` `Interval (s)` |
| **Swipe Test (calibrate joystick)** | 从 `(Start X, Start Y)` 滑到 `(End X, End Y)`。**用来校准摇杆中心 + 推杆半径** —— 估摇杆中心、做一次小推动看角色是否走，逐步调到走得自然。结束时打印对应的 `JoystickConfig(...)` 一键复制 | `Start X` `Start Y` `End X` `End Y` `Duration (ms)` |

### 后台任务（Trigger）

| 工具 | 用途 |
| --- | --- |
| **Mobile Diagnosis Overlay** | 在 GUI 主画面叠加绿色识别框（角色头像、技能、协奏环、小地图、目标框等），实时显示 `mobile.in_team` / `mobile.has_target` / `mobile.capture` / `mobile.interaction` / `mobile.held_dirs` 等状态。读图用，不发任何输入。 |

### 推荐 stage-2 调试顺序

```
1. 命令行先跑 probe.py（不依赖 GUI）
   .venv\Scripts\python.exe -m plugins.mumu12.probe
   → 看到 MuMu 进程是否在跑、ADB 设备列表、wuwa 包名

2. python main_mobile.py 启动 GUI
   → 在 Settings 里把 Mobile Config -> Game Package Names 改成 probe 找出的真实包名（如默认那几个就够用，跳过）

3. 跑 GUI 里的 Probe ADB Connection
   → 验证 GUI 内的 og.device_manager 走通；看 capture_method 是 NemuIpc 还是 ADB

4. 启用 Mobile Diagnosis Overlay
   → 对照 MuMu 画面看哪些识别框错位

5. 反复跑 Tap Test
   → 一个一个找出 KEY_MAP 里的按钮坐标
   → 每个找到后，复制到 key_map.py

6. 跑 Swipe Test
   → 从 (0.18, 0.78) 起步往上推 0.10
   → 看角色走的对不对，调到合适的中心 + 半径
   → 写进 key_map.py 的 JOYSTICK
```

## 配置项（GUI 里 → Settings → Mobile Config）

| Key | 默认 | 说明 |
| --- | --- | --- |
| Game Package Names | `com.kurogame.wutheringwaves,com.kurogame.wutheringwaves.cn,com.kurogamestudio.wutheringwaves,com.kurogame.wutheringwaves.global,com.kurogame.mc` | 鸣潮 Android 包名候选；ok-script 按顺序试，第一个匹配就 ok。多开实例不需要改 |
| Show Diagnosis Overlay | `False` | 启用诊断叠加层 |

> **不再有的选项**：原来有 `ADB Port` / `Input Backend`。现在 ok-script 的 `EmulatorManager` 通过注册表自动发现 MuMu 安装位置和 player_id（端口随之确定），`ADBInteraction` 自动按 capture method 选 NEMU IPC / uiautomator2 / `input swipe`。

## 已知限制

| 限制 | 影响 | 应对 |
| --- | --- | --- |
| key_map 没填全 | 触发未映射的按键时，日志打 `[mobile-key-map TODO] key='xxx'` 后丢弃 | 填 `key_map.py` |
| 视觉资产仍是 PC 端模板 | 部分图标在手游 UI 里位置 / 形状不同，识别可能失准 | 启用 `MobileDiagnosisTask` 看哪些 box 错位，必要时补抓手游模板（注意：会动 `assets/`） |
| 多 ADB 设备冲突 | "more than one device/emulator" 错误 | ok-script 自己就用 `-s <serial>`，理论上不冲突；如仍冲突，断开其它模拟器或在 GUI 里 Choose Device 明确选 MuMu |
| swipe 模拟摇杆 ≠ 真按住 | 走位需要持续 pump（每 ~300ms 一次 swipe）；动作切换有 swipe 的尾巴 | 实际跑起来再看是否够用；不够再切到 NemuIpc.down/move/up 直驱（ok-script 已实现，但要切到只走 NEMU IPC 模式） |

## 调试小抄

```bash
# 验证 ADB 是否能通到 MuMu
adb connect 127.0.0.1:16384
adb -s 127.0.0.1:16384 shell wm size

# 直接发个测试 tap（绕过 plugin）
adb -s 127.0.0.1:16384 shell input tap 500 500

# 找鸣潮的真实包名
adb -s 127.0.0.1:16384 shell pm list packages | grep -i kuro

# 一键诊断
.venv\Scripts\python.exe -m plugins.mumu12.probe
```

启用 `MobileDiagnosisTask` 后，GUI 主画面上会叠加绿色的识别框 + 在 info 面板显示 `mobile.in_team`、`mobile.has_target`、`mobile.capture`、`mobile.interaction`、`mobile.held_dirs` 等运行时状态。

## 不做的事

- ❌ 不支持 MuMu 12 以外的模拟器（架构允许扩展，但故意不做）
- ❌ 不重抓视觉资产（视觉效果不好时再说）
- ❌ 不修改 ok-script 框架本身（只用其公开 API）
