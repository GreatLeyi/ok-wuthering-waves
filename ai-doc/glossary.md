# Glossary — 中英文术语对照

代码里**统一用英文**作为方法名/标识符。中文只出现在：日志的额外说明、面向玩家的描述、中文 OCR 匹配字符串。

## 战斗系统

| 英文（代码） | 中文（游戏内） | 说明 |
| --- | --- | --- |
| `click` | 普通攻击 | 鼠标左键 |
| `heavy` / `heavy_attack` | 重击 | 长按左键 |
| `resonance` | 共鸣技能 | 默认键 `e`，由 `Game Hotkey Config.Resonance Key` 决定 |
| `echo` | 声骸技能 | 默认键 `q`，由 `Game Hotkey Config.Echo Key` 决定 |
| `liberation` | 共鸣解放（大招） | 默认键 `r`，由 `Game Hotkey Config.Liberation Key` 决定 |
| `forte` | 共鸣回路 | 角色专属能量/层数（如 Verina 4 段、Camellya 花苞 budding） |
| `intro` | 入场技 | 协奏值满后切人触发 |
| `outro` | 退场技 | 当前角色切出去时触发 |
| `concerto` / `con` | 协奏值 | 满了允许触发 intro；`is_con_full()` / `get_current_con()` |
| `dodge` | 闪避 | 默认键 `lshift`（`Dodge Key`） |
| `jump` | 跳跃 | 默认键 `space`（`Jump Key`） |
| `tool` | 探索工具 | 默认键 `t`（`Tool Key`） |
| `wheel` / `levitator` | 滑翔伞 / 浮空轮盘 | 默认键 `tab`（`Wheel Key`） |
| `f_break` | F 键打断 | 敌人架势条满时按 F 处决 |

## 角色/队伍

| 英文 | 中文 |
| --- | --- |
| `char_1 / char_2 / char_3` | 队伍 1/2/3 号位 |
| `Healer` | 治疗位（如 Verina、Shorekeeper、Baizhi、Youhu） |
| `MAIN_DPS` / `SUB_DPS` | 主 C / 副 C |
| `Priority` | 切人优先级枚举 |
| `Element` | 元素属性：SPECTRO 衍射 / ELECTRIC 导电 / FIRE 热熔 / ICE 冷凝 / WIND 气动 / HAVOC 湮灭 |
| `ring_index` | 协奏值环对应的元素 index |

## 任务/场景

| 英文 | 中文 | 备注 |
| --- | --- | --- |
| `Daily Task` | 一条龙 | `DailyTask`：登录→月卡→刷副本→领日常 |
| `Tacet Suppression` | 残象抑制 | `TacetTask` |
| `Forgery Challenge` | 凝素领域 / 模拟领域 | `ForgeryTask` |
| `Simulation Challenge` | 全息战略模拟 | `SimulationTask` |
| `Nightmare Nest` | 梦魇巢 | `NightmareNestTask` |
| `Farm Echo` | 刷声骸 | `FarmEchoTask` |
| `Auto Rogue` | 无音清剿（半自动） | `AutoRogueTask` |
| `Domain` | 副本入口 | `DomainTask` |
| `Illusive Realm` | 幻象空间 / 迷幻领域 | `in_realm()` 检测 |
| `Tower` | 周本入口（深境之塔） | `go_to_tower()` |
| `Way Point / Teleport` | 传送点 | 地图上的图钉 |
| `Monthly Card` | 月卡 | 每天 04:00 弹窗 |
| `Battle Pass` | 战令 | 每日领取 |
| `Stamina` | 体力（结晶波片） | `get_stamina()` |
| `Echo Drop` | 声骸掉落 | YOLO 检测 + F 吸收 |

## UI / 界面

| 英文 | 中文 |
| --- | --- |
| `claim` | 领取奖励 |
| `confirm_btn` | 确认按钮 |
| `cancel_button` | 取消按钮 |
| `gray_book` | 书 / 索敌册（F2 打开） |
| `pick_up_f` | F 键拾取提示 |
| `revive_confirm` | 复活确认弹窗 |
| `dialog_3_dots` | 对话三点（NPC 对话中） |
| `skip_dialog` | 跳过剧情 |
| `treasure_icon` | 宝箱图标 |
| `world_earth_icon` | 世界图标（确认在大世界） |

## 颜色 / 图像处理

| 英文 | 含义 |
| --- | --- |
| `f_white_color` | F 键提示的白色像素范围（拾取就绪时） |
| `text_white_color` | 通用 UI 白色文字（识别技能可用性） |
| `convert_bw` | 转黑白用于二值匹配 |
| `binarize_for_matching` | 自适应二值化 |
| `isolate_white_text_to_black` | 把白色文字隔离成黑底（CD 数字识别用） |
| `make_bottom_right_black` | `config.screenshot_processor`：每帧把右下角的小地图坐标遮掉，避免文本干扰 |

## 截屏 / 窗口

| 英文 | 含义 |
| --- | --- |
| `WGC` | Windows.Graphics.Capture，Win10+ 优先用 |
| `BitBlt_RenderFull` | GDI BitBlt 全帧截图（fallback） |
| `PostMessage` | 后台输入注入（不抢前台） |
| `HDR / Night Light` | HDR / 夜间模式（要求关掉以保证识别准确） |
| `hwnd` / `top_hwnd_class` | 游戏 / 启动器窗口类名匹配 |

## 不要混用的几个词

- **echo** ≠ **Echo Skill**：
  - 大写 *Echo* / `echo_key` 指**声骸技能**（按键）。
  - `find_echos()` / `pick_echo()` 指地上的**声骸掉落物**。
- **forte** ≠ **Concerto**：
  - forte = 共鸣回路（角色技能层数/能量）。
  - concerto = 协奏值（队伍切人能量）。
- **realm** ≠ **domain**：
  - realm = 幻象空间（特殊场景，自动检测）。
  - domain = 一般副本（凝素领域、声之领域等）。
