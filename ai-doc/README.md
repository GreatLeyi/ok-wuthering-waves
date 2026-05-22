# ai-doc

本目录用于存放 **面向 AI 协作者** 的项目文档与素材。

人类阅读的文档请见仓库根目录的 `README.md` / `README_en.md`。本目录的资料是为了让 AI（如 Claude / Codex / GPT 等）在没有上下文的情况下，能够 **快速、准确** 地理解本项目，并在编辑代码时遵守现有约定。

## 文件索引

| 文件 | 用途 |
| --- | --- |
| `project-overview.md` | 项目总览：用途、技术栈、目录结构、关键抽象、运行入口、典型任务流。**新 AI 进来后第一份要读的文档。** |
| `tech-stack-and-algorithms.md` | 技术栈逐项展开 + 关键算法/流程详解（视觉三管线、战斗状态机、Priority 切人、freeze 时间补偿、协奏环检测、走路/复活/月卡流程图）。看完 overview 紧接着读这篇。 |
| `glossary.md` | 中英文术语表（声骸 = echo、共鸣技能 = resonance、共鸣回路 = forte、共鸣解放 = liberation 等）。 |
| `conventions.md` | 编码与项目约定：任务/角色注册、Labels、虚拟环境、commit 规范、不允许做的事。 |
| `mobile-port-plan.md` | **进行中**：让 ok-ww 跑在 MuMu 12 上的架构决策记录 + 实施 plan。看到此条目说明项目正在做手游模拟器适配；下次接手时从这里继续。 |

## 已有的 AI 资料（不在本目录）

仓库里已经存在另外一些 AI 相关资料，**请优先复用，不要重复创建**：

- `AGENTS.md` —— 全局 agent 说明（要求用本地 `.venv`）。
- `.agent/skills/` —— 项目自带的技能定义，包含具体的实现模板和检查清单：
  - `ok-ww-characters/` —— 新增/修改 `src/char/` 下角色类时使用。
  - `ok-script-tasks/` —— 新增/修改 `src/task/` 下任务时使用。
  - `ok-script-i18n/` —— 翻译 `i18n/<locale>/LC_MESSAGES/ok.po` 时使用。
  - `use-local-venv/` —— 调用 Python 时统一走 `.venv`。

> 触发对应技能的写法（Codex/Claude）：在用户/任务描述里出现"添加角色 / 新增任务 / 翻译 po / 编译 mo"等关键字时，技能会自带详细模板，**不要重新发明轮子**。

## 在这里追加内容时的约定

1. 文档面向 AI，**简洁、可机读**。能用列表/表格就别写散文。
2. 每份新文档在本 README 的 **文件索引** 表中登记一行。
3. 不放秘密信息（账号、token、私人配置）。
4. 不放体积大的二进制（截图请用 `assets/` 或 `readme/`）。
5. 内容若与 `.agent/skills/` 重复，请改为在本目录链接过去而不是复制。
