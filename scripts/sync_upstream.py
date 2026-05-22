#!/usr/bin/env python3
"""Sync upstream into this fork, then push to origin.

This is the machine half of the "AI handles fork sync" workflow described
in ``CLAUDE.md``.  Run it from anywhere; it locates the repo root via git.

What it does, in order:

1. ``git fetch upstream`` (and ``origin`` so we know if origin is also ahead).

2. **Mirror upstream's README files into our README_upstream*.md.**  Whenever
   upstream changes ``README.md`` / ``README_en.md``, we capture the new
   content and write it into ``README_upstream.md`` / ``README_upstream_en.md``
   *before* attempting the merge.  This way our own ``README.md`` (the
   vibe-fork one) survives, and the upstream content goes into the right
   place automatically.

3. ``git merge upstream/<default>``.  The fork-vs-upstream README rename
   guarantees a conflict on ``README.md`` / ``README_en.md`` every time
   upstream touches them; we auto-resolve those by keeping *ours* (since
   step 2 already saved upstream's content into the mirror file).

4. **Stop on any other conflict** -- those need human / AI judgement.

5. If everything merged cleanly and ``--push`` was passed, push to origin.

Usage::

    python scripts/sync_upstream.py            # fetch + merge, no push
    python scripts/sync_upstream.py --push     # fetch + merge + push
    python scripts/sync_upstream.py --dry-run  # show what would happen

Exit codes:
    0  -- nothing to do, OR sync succeeded
    1  -- conflicts that need manual resolution
    2  -- pre-flight failure (no upstream remote, dirty tree, etc.)
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
from typing import List, Optional


# Filenames in the fork that "shadow" an upstream filename.  When upstream
# changes the LHS, we mirror its new content into the RHS, then keep ours
# on the merge.  Add more pairs here if you ever rename more upstream files.
SHADOWED_FILES = [
    ('README.md',    'README_upstream.md'),
    ('README_en.md', 'README_upstream_en.md'),
]


def repo_root() -> pathlib.Path:
    """Return the absolute path of the git repo containing this script."""
    out = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return pathlib.Path(out)


ROOT = repo_root()


def run(args: List[str], *, capture: bool = False, check: bool = True
        ) -> subprocess.CompletedProcess:
    """Run a git/subprocess command in the repo root.

    Forces UTF-8 decoding regardless of host locale.  Without this,
    Windows' default GBK codec chokes on Chinese commit messages /
    file paths in git output (UnicodeDecodeError).
    """
    return subprocess.run(
        args, cwd=ROOT,
        capture_output=capture, text=True,
        encoding='utf-8', errors='replace',
        check=check,
    )


def show_upstream_file(ref: str, path: str) -> Optional[str]:
    """Return the contents of <ref>:<path>, or None if it doesn't exist there."""
    r = subprocess.run(
        ['git', 'show', f'{ref}:{path}'],
        cwd=ROOT, capture_output=True, text=True,
        encoding='utf-8', errors='replace',
    )
    return r.stdout if r.returncode == 0 else None


def upstream_default_branch() -> str:
    """Find the upstream remote's default branch via symbolic-ref."""
    # `git remote show upstream` is slow (network); use the HEAD pointer
    # we already have locally.
    r = subprocess.run(
        ['git', 'symbolic-ref', '--short', 'refs/remotes/upstream/HEAD'],
        cwd=ROOT, capture_output=True, text=True,
    )
    if r.returncode == 0 and r.stdout.strip():
        # e.g. "upstream/master" -> "master"
        return r.stdout.strip().split('/', 1)[1]
    # Fallback: try common names
    for cand in ('master', 'main'):
        r = subprocess.run(
            ['git', 'rev-parse', '--verify', f'upstream/{cand}'],
            cwd=ROOT, capture_output=True, text=True,
        )
        if r.returncode == 0:
            return cand
    raise SystemExit('Cannot determine upstream default branch.')


def working_tree_clean() -> bool:
    r = run(['git', 'status', '--porcelain'], capture=True)
    return r.stdout.strip() == ''


def conflicted_files() -> List[str]:
    r = run(['git', 'diff', '--name-only', '--diff-filter=U'],
            capture=True, check=False)
    return [line.strip() for line in r.stdout.splitlines() if line.strip()]


def merge_in_progress() -> bool:
    return (ROOT / '.git' / 'MERGE_HEAD').exists()


def do_sync(push: bool, dry_run: bool) -> int:
    # ---- Pre-flight ------------------------------------------------------
    remotes = run(['git', 'remote'], capture=True).stdout.split()
    if 'upstream' not in remotes:
        print('ERROR: no "upstream" remote configured.', file=sys.stderr)
        print('       Add one with:', file=sys.stderr)
        print('         git remote add upstream '
              'https://github.com/ok-oldking/ok-wuthering-waves.git',
              file=sys.stderr)
        return 2

    if not working_tree_clean():
        print('ERROR: working tree has uncommitted changes.', file=sys.stderr)
        print('       Commit or stash first.', file=sys.stderr)
        return 2

    if merge_in_progress():
        print('ERROR: a merge is already in progress.  Resolve or abort it '
              'first (`git merge --abort`).', file=sys.stderr)
        return 2

    # ---- Step 1: fetch ---------------------------------------------------
    print('==> git fetch upstream')
    if not dry_run:
        run(['git', 'fetch', 'upstream'], check=False)
    print('==> git fetch origin')
    if not dry_run:
        run(['git', 'fetch', 'origin'], check=False)

    upstream_branch = upstream_default_branch()
    upstream_ref = f'upstream/{upstream_branch}'
    print(f'    upstream default branch: {upstream_branch}')

    # Are we even behind?
    behind = run(['git', 'rev-list', '--count', f'HEAD..{upstream_ref}'],
                 capture=True).stdout.strip()
    ahead = run(['git', 'rev-list', '--count', f'{upstream_ref}..HEAD'],
                capture=True).stdout.strip()
    print(f'    HEAD is {ahead} ahead, {behind} behind {upstream_ref}')
    if behind == '0':
        print('==> already up to date with upstream.')
        if push:
            return _maybe_push(dry_run)
        return 0

    # ---- Step 2: mirror shadowed files BEFORE merging --------------------
    print('==> mirroring upstream README files into README_upstream*.md')
    mirror_changed = False
    for upstream_name, mirror_name in SHADOWED_FILES:
        new_content = show_upstream_file(upstream_ref, upstream_name)
        if new_content is None:
            print(f'    {upstream_name}: not present upstream, skipping')
            continue
        mirror_path = ROOT / mirror_name
        old_content = (
            mirror_path.read_text(encoding='utf-8')
            if mirror_path.exists() else ''
        )
        if old_content == new_content:
            print(f'    {upstream_name}: unchanged, mirror already matches')
            continue
        print(f'    {upstream_name}: CHANGED -> writing to {mirror_name}')
        if not dry_run:
            mirror_path.write_text(new_content, encoding='utf-8')
        mirror_changed = True

    if mirror_changed and not dry_run:
        run(['git', 'add'] + [m for _, m in SHADOWED_FILES
                              if (ROOT / m).exists()])
        # Commit the mirror sync as its own change so the merge doesn't
        # have to reason about it.  Keep the message machine-greppable.
        run(['git', 'commit', '-m',
             f'chore(sync): mirror upstream README into README_upstream*.md '
             f'({upstream_ref})'])

    # ---- Step 3: merge ---------------------------------------------------
    print(f'==> git merge --no-edit {upstream_ref}')
    if dry_run:
        print('    (dry-run; skipping actual merge)')
        return 0

    merge = run(['git', 'merge', '--no-edit', upstream_ref], check=False)
    if merge.returncode == 0:
        print('==> merged cleanly.')
        if push:
            return _maybe_push(dry_run)
        return 0

    # ---- Step 4: auto-resolve shadowed files, escalate the rest ----------
    conflicts = conflicted_files()
    print(f'    conflicts: {conflicts}')

    auto = []
    for upstream_name, _ in SHADOWED_FILES:
        if upstream_name in conflicts:
            run(['git', 'checkout', '--ours', upstream_name])
            run(['git', 'add', upstream_name])
            auto.append(upstream_name)
            conflicts.remove(upstream_name)
    if auto:
        print(f'    auto-resolved (kept ours): {auto}')

    if conflicts:
        print()
        print('========================================================')
        print('CONFLICTS REMAIN -- handing off to AI / human:')
        for c in conflicts:
            print(f'  - {c}')
        print()
        print('Resolution options:')
        print('  - Edit each file to fix the <<<<<< / >>>>>> markers.')
        print('  - Or `git checkout --ours <file>` / `--theirs <file>`')
        print('    if one side wins outright.')
        print('  - Then `git add <file>` and `git merge --continue`.')
        print('========================================================')
        return 1

    # All conflicts auto-resolved -- finalize.
    print('==> git merge --continue')
    cont = run(['git', 'commit', '--no-edit'], check=False)
    if cont.returncode != 0:
        # Some git versions need `merge --continue` instead.
        run(['git', 'merge', '--continue'])
    print('==> sync complete.')

    if push:
        return _maybe_push(dry_run)
    return 0


def _maybe_push(dry_run: bool) -> int:
    """Push HEAD to origin's tracking branch."""
    print('==> git push origin HEAD')
    if dry_run:
        print('    (dry-run; skipping push)')
        return 0
    r = run(['git', 'push', 'origin', 'HEAD'], check=False)
    return 0 if r.returncode == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--push', action='store_true',
                        help='Push to origin after a successful sync.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would happen, do not modify the repo.')
    args = parser.parse_args()
    return do_sync(push=args.push, dry_run=args.dry_run)


if __name__ == '__main__':
    sys.exit(main())
