# Session Resume — 2026-05-22

> 如果你是接手这个会话的 AI（或重启 shell 后回来的同一个会话），
> **先读这一份**。看完之后再读 [`CLAUDE.md`](../CLAUDE.md) 的 Rules
> 和 [`mobile-port-plan.md`](mobile-port-plan.md) 的架构。
>
> 任务全部跑完后，把这个文件删了（或归档进 `ai-doc/archive/`）。

---

## TL;DR

我们在做一个 vibe-coding 的 fork，让 ok-ww 跑 MuMu 12 上的鸣潮手游。
Plugin 框架已落地、ok-script 自带 ADB 模式的关键 bug 已 monkey-patch、
`key_map.py` 已经填好（坐标从 MuMu 自带键鼠 overlay 抠出来的、不是
试错来的）。

剩下的工作主要有三大块：

1. **仓库私有化迁移** —— 用户卡在这一步，等他建新私有仓库
2. **真机校准/烟测** —— 走完登录、tap 验证几个关键 key_map 坐标
3. **`main_mobile.py` 启动验证** —— 跑一次 GUI 看 IPC patch 是否生效

---

## Git 状态（截至 506b28e）

- HEAD = `origin/master` = `506b28e docs(claude): 加 Rule 0 + Rule 7 隐私硬约束 + 修 Rule 6 重复`
- 工作树干净，没有 uncommitted / unpushed
- 上游 `upstream/master` = 已自动 merge 进来（最近一次 cba37b6）
- Push 流程已经稳定：每次推送都过 `python scripts/sync_upstream.py --push`
  自动同步 upstream

---

## 重要的状态（不在代码里的）

### 1. 仓库要从 fork 迁到独立私有仓库（**待用户操作**）

GitHub 不允许直接把 fork 改成 private（"For security reasons, you
cannot change the visibility of a fork."）。所以方案是：

1. 用户去 https://github.com/new 建一个**私有的、不勾任何初始化项**
   的新仓库（建议命名 `ok-ww-mobile`）
2. 用户把新仓库 URL 贴给 AI
3. AI 跑：
   ```bash
   git remote rename origin origin-old
   git remote add origin <新仓库 URL>
   git push -u origin master --tags
   ```
4. 验证新仓库可访问后，用户去老 fork
   `https://github.com/GreatLeyi/ok-wuthering-waves/settings`
   底部 Danger Zone 删除老仓库
5. AI 同步更新 `CLAUDE.md` 里的 origin URL（Rule 0）

**为什么这样做**：用户希望仓库私有以避免泄漏隐私。已确认现有 commit
都是 PII-clean 的（grep 过 "5872" 等关键词，全是无关的坐标数字
误匹配）。

### 2. WuWa Mobile 当前正卡在登录弹窗（**等用户重启完 shell**）

最后一次 `wuwa_capture.py` 的画面：KURO GAMES 登录 dialog，记忆了
上次账号。用户告诉我：

- 当前屏幕：登录弹窗，"登录" 按钮在 dialog 中央
- 登录后：进 "两个角色站位" 的过场屏（**点屏幕任意位置**进入游戏）
- 进游戏后：开放世界 HUD（之前来过 —— 阶梯 + 角色站立的场景）

**继续校准的下一动作（重启 shell 之后做）**：
1. `python scripts/wuwa_capture.py --out tmp/now.png` 看现在啥状态
2. 如果还在登录弹窗：tap (0.50, 0.55) 是登录按钮（**估计值，需要从图里再确认**）
3. 等到 stable，应该到 "两人过场" 屏，tap (0.50, 0.50) 任意位置
4. 等 stable，应该回到开放世界
5. 此时可以**抽查 key_map**：
   - tap M 地图位置 (0.107, 0.167) → 截图 → 看地图是否打开 → 找视觉上的 X 关闭
   - tap E 共鸣战技 (0.719, 0.898) → 截图 → 看角色是否做出技能动作（注意：这要在战斗或非和平区）

### 3. main_mobile.py GUI 还没重启验证（task #43）

- 用户上次跑 `python main_mobile.py` 时，IPC capture 因 ok-script
  bug 报 `AttributeError: 'NemuIpcCaptureMethod' object has no
  attribute 'screencap'`，GUI 卡在 "Starting"
- 这个 bug 已经在 commit `7042f5e` monkey-patch 了
- **需要用户重启 `main_mobile.py` 验证 fix 生效**（不能由 AI 验证，
  AI 起 GUI 也不能"看"GUI 状态）
- 验证内容：
  - 控制台不再报 `screencap` 错
  - GUI 里点 Probe ADB Connection 任务的 Start，info panel 能输出
    `adb.serial`/`adb.wm_size`/`adb.capture_method` 等
  - capture_method 应该显示 `NemuIpcCaptureMethod`（不是 fallback ADB）

---

## 当前 task 列表的状态

```
#32-38: completed（架构落地 + ok-script ADB 模式整合 + 校准基建）
#40    in_progress: Smoke-test main_mobile.py end-to-end（等用户重启 GUI）
#41    completed:   AI-driven key_map.py calibration via wuwa_* scripts
                    （坐标已填，但 tap 验证还没做 —— 等登录后做）
#43    pending:     Verify GUI no longer hangs after IPC patch
                    （依赖 task #40 ）
```

---

## 已知陷阱（别再踩）

| 陷阱 | 后果 | 怎么避免 |
| --- | --- | --- |
| 连按 `KEYCODE_BACK` | 游戏一路退到登录屏，重连要等 ~60s | CLAUDE.md Rule 6：禁用 BACK |
| 截图含登录账号信息直接 commit | 隐私泄漏 | CLAUDE.md Rule 7：tmp/ 已 gitignore，不要往 tracked 目录写 |
| 改 fork 仓库可见性 | GitHub 拒绝 | 必须新建独立私有仓库 |
| 在 dirty 工作树上跑 sync_upstream.py | 报错 | 先 commit 或 stash |
| 编辑 `key_map.py` 后想看效果 | Python import 缓存，必须重启 main_mobile.py | 文件改完重启 |

---

## 你（AI）回来要做的第一件事

```bash
# 1. 看自己上次推到哪了
cd F:/ok-wuthering-waves
git log --oneline -3
# 期望：506b28e ... 是最新

# 2. 确认 git 干净
git status --short
# 期望：空

# 3. 看一眼用户在重启之前给过你哪些消息（聊天历史）
#    特别是：新仓库 URL 是否给了？

# 4. 如果新仓库 URL 已给 → 走 "1. 仓库迁移" 步骤
#    如果没给 → 提醒用户：新仓库 URL 还没给我

# 5. 如果用户希望先继续校准而不是迁移，
#    则 python scripts/wuwa_capture.py --out tmp/now.png 看 WuWa 当前状态
```

记住：每个 Bash call 用户都要授权，所以**能合并就合并**（CLAUDE.md
Rule 5）。`tmp/` 截图随用随删，别留。

---

## 用户偏好（学习到的）

- 喜欢一次授权大批量操作，讨厌每步弹确认
- 接受 commit + push 全自动（已通过 "今后的更新...都交给 AI 完成"
  授权）
- 隐私敏感（手机号 / 账号 / KURO 信息一律不能写到 tracked 文件 /
  commit message / 状态机文档）
- 希望 AI 主动驱动 WuWa（启动游戏、点登录、走流程都让 AI 做）
- 写诊断/技术文档时偏好双语，但 commit message 中文为主
