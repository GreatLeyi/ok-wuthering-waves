# CLAUDE.md -- ground rules for AI agents working in this fork

This file is read automatically by Claude Code (and similar agents) when
they start in this repo.  Treat it as **non-negotiable behaviour**: every
AI session should follow these rules, regardless of what the user asks.

---

## What this project is

`ok-wuthering-waves` upstream is a PC-only Wuthering Waves automation tool.
This fork adds **MuMu Player 12 mobile-mode support** as a pluggable
[`plugins/mumu12/`](plugins/mumu12/) package + a 5-line
[`main_mobile.py`](main_mobile.py) entrypoint.  The upstream code in
`src/`, `main.py`, `main_debug.py`, `config.py`, `assets/`, `ok_templates/`
is **never modified**.  Background, design, and decisions live in
[`ai-doc/`](ai-doc/) -- read those before non-trivial work.

The fork's user-facing README is the new top-level [`README.md`](README.md);
the upstream Chinese / English READMEs are preserved as
[`README_upstream.md`](README_upstream.md) and
[`README_upstream_en.md`](README_upstream_en.md).

---

## Rule 1: never modify upstream code

Hard constraint.  Files under any of these paths are **off limits**:

- `src/`
- `main.py`, `main_debug.py`, `config.py`
- `assets/`, `ok_templates/`
- The ok-script package itself (under `.venv/`)

If a feature seems to require upstream changes, stop and re-architect
through `plugins/mumu12/`.  Past examples of how to inject without
touching upstream code:

- Replace `config['windows']` with `config['adb']` in
  `plugins/mumu12/__init__.py::apply_to`
- Wrap task classes via MRO injection in
  `plugins/mumu12/task_wrapper.py::wrap_task_entry` so PC keyboard calls
  route through the mixin without changing the original task source

---

## Rule 2: sync upstream BEFORE every push

**You must run `python scripts/sync_upstream.py` before pushing to origin.**
This applies whether the user asks for a push directly, or you decide a
push is the right thing to do as part of a larger task.

The flow is:

```
git add ... && git commit ...           # whatever changes you made
python scripts/sync_upstream.py --push  # fetch upstream, merge, push
```

Or two-stage if you want to inspect first:

```
python scripts/sync_upstream.py         # fetch + merge, no push
# review with: git log --oneline @{u}..HEAD
git push origin HEAD                    # push manually after confirming
```

What the sync script handles automatically:

| Situation | Script behaviour |
| --- | --- |
| Upstream is unchanged | No-op, reports "already up to date" |
| Upstream's `README.md` / `README_en.md` changed | Mirrors new content into `README_upstream.md` / `README_upstream_en.md` (commit message starts with `chore(sync):`), then merges the rest |
| Merge produces conflicts on `README.md` / `README_en.md` only | Auto-resolves by keeping ours (the fork README); upstream's content already landed in `README_upstream*.md` in the previous step |
| Merge produces other conflicts | Stops, prints the conflict list, exits 1 -- AI takes over from there |
| Working tree dirty | Refuses to start -- you must commit/stash first |

**Do not bypass this script** by calling `git push` directly unless the
user explicitly says so.  The script's purpose is to keep the fork close
to upstream without burying upstream README changes inside our fork
README.

## Rule 2a: how to resolve non-README conflicts

When the sync script exits 1 with a conflict list, the rule is:

- **Conflicts in `src/`, `main.py`, `config.py`, `assets/`, `ok_templates/`**:
  these directories are off-limits for fork edits (Rule 1), so any
  conflict means upstream changed a file we never touched.  Default to
  `git checkout --theirs <file>` (take upstream's version), then
  `git add <file>`.

- **Conflicts in `plugins/mumu12/`, `ai-doc/`, `main_mobile.py`,
  `build.bat`, `scripts/`, `CLAUDE.md`, `README.md`, `.gitignore`**:
  these are fork-owned.  Default to `git checkout --ours <file>`, then
  `git add <file>`.

- **Anything else**: read both sides, reason about the intent, and
  produce a merged version manually.

After resolving every conflict, run `git merge --continue`, then re-run
`python scripts/sync_upstream.py --push` to finish.

---

## Rule 3: commit messages

- Plain English / Chinese, imperative mood, focus on *why*.
- Co-author trailer is fine but **not required**; do not skip hooks
  (`--no-verify`) or skip signing without an explicit user request.
- The sync script's auto-commits use `chore(sync): ...` -- don't squash
  or amend those; they're the audit trail of what came from upstream.

## Rule 4: don't push to upstream

`git remote -v` lists both `origin` (the fork) and `upstream` (the
original `ok-oldking/ok-wuthering-waves`).  **Never push to `upstream`**.
The sync script only pushes to `origin`; if you write any other
push-related code, hard-code the remote name to `origin`.

## Rule 5: prefer the wuwa_* scripts over inline ADB calls

Stage-2 calibration is heavily delegated to the AI: the user opens
MuMu, the AI launches WuWa, takes screenshots, identifies on-screen
buttons, fills `key_map.py`, taps to verify, then commits.  To make
that flow stable across sessions, three reusable scripts live in
`scripts/`:

| Script | Purpose |
| --- | --- |
| `scripts/wuwa_capture.py` | Screenshot to PNG.  Optional `--launch` to start WuWa, `--wait-stable N` to poll until 3 successive frames match (boot/loading detection), `--info` for getprop dump. |
| `scripts/wuwa_tap.py rel_x rel_y` | Tap relative coords (0..1).  Optional `--capture-after PATH` to take a follow-up screenshot in the same call. |
| `scripts/wuwa_swipe.py sx sy ex ey [--duration ms]` | Swipe between relative coords; same `--capture-after` option. |

Use these instead of inline `python -c "import adbutils; ..."` blocks
so the user only has to authorise predictable `python scripts/wuwa_*`
commands once.  All three share `scripts/_adb_common.py` for ADB
device discovery (auto-detects MuMu's `127.0.0.1:1638X` serial
pattern).

**The AI calibration flow looks like:**

```bash
# Boot WuWa, save first stable screenshot
python scripts/wuwa_capture.py --launch --wait-stable 90 --out tmp/boot.png

# AI reads tmp/boot.png via Read tool, identifies buttons, then:
python scripts/wuwa_tap.py 0.93 0.85 --capture-after tmp/after_e.png
# AI reads tmp/after_e.png, confirms the resonance button highlighted,
# updates plugins/mumu12/key_map.py.

# Joystick calibration:
python scripts/wuwa_swipe.py 0.18 0.78 0.18 0.68 --duration 800 \
    --capture-after tmp/after_swipe.png
# AI compares before/after to see if character moved, refines JoystickConfig.
```

When you finish a calibration round: edit `key_map.py`, commit, then
`python scripts/sync_upstream.py --push` (Rule 2 still applies).

---

```bash
# Sync without pushing (default; safe to run anytime)
python scripts/sync_upstream.py

# Sync + push (typical end-of-session call)
python scripts/sync_upstream.py --push

# See what would happen without changing anything
python scripts/sync_upstream.py --dry-run

# Inspect upstream changes since our last sync
git log --oneline HEAD..upstream/master

# Inspect what we have on top of upstream
git log --oneline upstream/master..HEAD
```

---

## File map for AI orientation

| Where | What |
| --- | --- |
| `README.md` | Fork README (the "vibe coding" one); user-facing |
| `README_upstream.md`, `README_upstream_en.md` | Mirror of upstream READMEs; auto-updated by `scripts/sync_upstream.py` |
| `ai-doc/` | Architecture & decision records.  **Read before non-trivial work.** |
| `plugins/mumu12/` | All fork code lives here |
| `main_mobile.py` | Mobile-mode entrypoint (5 lines, swaps in `apply_to(config)`) |
| `scripts/sync_upstream.py` | The sync tool you must run before pushing |
| `build.bat` | Self-bootstrapping build (auto-installs Python 3.12 if missing) |
| `CLAUDE.md` | This file |

If something seems missing, search `ai-doc/` first -- there's a good
chance the answer is documented there.
