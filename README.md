# ok-wuthering-waves（vibe 尝试：支持模拟器）

> ⚠️ **这是一份纯 vibe coding 的尝试**，目标是让上游 [ok-ww](README_upstream.md) 在 **MuMu Player 12** 模拟器里跑**手游版鸣潮**。
>
> 不保证质量，不保证能跑通，不保证不弄坏你的存档。**用之前请自己看代码。**

---

## 这是啥

[ok-ww](https://github.com/ok-oldking/ok-wuthering-waves) 是一个基于图像识别的鸣潮自动化工具，**只支持 PC 端**鸣潮（Windows 客户端）。

我想让它**额外**支持手游版鸣潮在 MuMu 12 模拟器里跑，但**不修改原作者的任何代码**。整个改动以 plugin 形式塞在 [`plugins/mumu12/`](plugins/mumu12/) 里 + 一个 thin 新入口 [`main_mobile.py`](main_mobile.py)。

> 完整设计文档：[`ai-doc/mobile-port-plan.md`](ai-doc/mobile-port-plan.md)
> 插件自述：[`plugins/mumu12/README.md`](plugins/mumu12/README.md)

## 为啥说"纯 vibe"

- 全程 AI 辅助 vibe coding，没做严格的设计评审 / 单元测试 / 大规模实测
- 视觉资产（图标识别模板）**仍然用 PC 端的**，手游 UI 不一致的部分识别会失准
- 关键映射（手游里每个虚拟按钮的屏幕坐标）**用户得自己用 GUI 里的校准任务一个一个找**，没有现成的
- 摇杆模拟用的是周期性 swipe，不是真正的 multi-touch 长按；快速换向不一定干净
- 只测过 MuMu 12，雷电/夜神/BlueStacks 一律没管

## 怎么跑

```bash
# 拉项目 + 准备依赖（自动下载 Python 3.12.13 if 系统没有）
build.bat

# PC 端鸣潮（上游本来就支持，本仓库不改它）
python main.py

# MuMu 12 手游版（本仓库新增）
python main_mobile.py
```

第一次跑 mobile 模式之前，先做这些：

1. **跑命令行 probe**（不依赖 GUI，先验证基础设施）：
   ```bash
   .venv\Scripts\python.exe -m plugins.mumu12.probe
   ```
   它会列出 MuMu 进程、ADB 设备、设备上的鸣潮包名。

2. **填 [`plugins/mumu12/key_map.py`](plugins/mumu12/key_map.py)**（全部 TODO）。用 GUI 里 **Mobile** group 下的 **Tap Test** 和 **Swipe Test** 任务交互式找坐标，然后手动写进文件。

3. 启用 **Mobile Diagnosis Overlay** 看识别框是否对齐手游 UI。

## 完全卸载（恢复成纯上游）

```bash
rm -rf plugins/mumu12 main_mobile.py ai-doc/ build.bat
mv README_upstream.md README.md
mv README_upstream_en.md README_en.md
```

`src/`、`config.py`、`main.py`、`main_debug.py`、`assets/`、`ok_templates/` 一行没动。

## 上游文档

原作者的中英文 README 没删，挪到这里了：

- 中文：[README_upstream.md](README_upstream.md)
- English：[README_upstream_en.md](README_upstream_en.md)

上游的所有功能（PC 端鸣潮自动化、自动登录、自动战斗、日常、声骸养成等）继续从上游 README 看。**本 fork 没动这些。**

## 致谢

- [ok-oldking/ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves) -- 上游本体
- [ok-oldking/ok-script](https://github.com/ok-oldking/ok-script) -- 底层框架（已经包含完整的 ADB / NEMU IPC / uiautomator2 支持，这个 fork 大部分时间是在"发现 ok-script 已经实现了我想做的事情"）

## 免责声明

本 fork 仅用于学习与研究 ok-script 的 plugin 架构，以及探索 vibe coding 跨设备移植的可行性。**任何因使用本 fork 导致的账号封禁、存档损坏、设备损坏均与本人无关。**
