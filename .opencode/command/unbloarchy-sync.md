---
description: Full Unbloarchy sync with upstream per UPSTREAM-SYNC.md: fetch upstream/quattro, branch, merge, resolve conflicts, rebrand sweep, regenerate shims, push, and open a PR. Ends only at the PR. Asks you whenever a decision is ambiguous.
agent: build
---

# Unbloarchy upstream sync (full process, per README.md)

Execute the entire procedure from the Unbloarchy repo checkout at
`../unbloarchy`. This sync repo contains the guide and helpers, and you invoke
those helpers from the Unbloarchy repo root. Read the guide in the Unbloarchy
repo and `AGENTS.md` at the repo root first. Whenever a decision is ambiguous
or not covered by the guide, ASK the user before proceeding.

## Locate things

- Repo root: prefer the current directory if `git rev-parse` succeeds there;
  otherwise try `../unbloarchy` or `./unbloarchy`. If still ambiguous, ask the
  user.
  - Helper scripts `sweep.py` + `transform.py`: they live in this sync repo, but
    you run them from the Unbloarchy repo root as
    `../unbloarchy-sync/sweep.py` and `../unbloarchy-sync/transform.py`. If not
    found, ask.
- Remotes: `origin` = the fork (`Magiclovekorean/unbloarchy`),
  `upstream` = `omacom/omarchy`. If `upstream` is missing, add
  `git@github.com:omacom/omarchy.git` and confirm with the user.

## Pre-flight

- If a merge is already in progress (`.git/MERGE_HEAD` exists or `git status`
  shows `|merge`), ASK the user: continue resolving here, or
  `git merge --abort` and restart cleanly? Never abort/reset without confirming.
- If the branch `sync/upstream-*` already exists on `origin`/locally for this
  tip, ask the user whether to reuse it (subsequent commit after an already
  pushed branch needs care), or start fresh.

## 1. Pick the tip and create the sync branch

```bash
git fetch upstream quattro
UP=$(git rev-parse --short upstream/quattro)
```

Ask the user which setup they want:
- **Option A — in place (default):** `git switch -c sync/upstream-$UP quattro`
- **Option B — worktree:** link the branch into a separate folder such as
  `../unbloarchy-sync-merge` and run the rest of this command from there;
  remember cleanup in step 6.

## 2. Merge upstream

```bash
git merge upstream/quattro
```

Expect conflicts in docs, tests, `applications.lua`, renamed `bin/` scripts,
etc. `Automatic merge failed; fix conflicts and then commit the result.` is
expected — it just means resolution isn't finished.

## 3. Resolve all conflicts

Enable base context: `git config merge.conflictstyle zdiff3`.

List them: `git diff --name-only --diff-filter=U`. Work until EMPTY.

### Reading the output

- `Auto-merging <path>` → done, nothing to do.
- `Resolved '<path>' using previous resolution.` → rerere re-applied an old
  choice and staged it; accept but review with `git diff --cached --stat`.
  Not automatically correct.
- `Recorded preimage for '<path>'` / `CONFLICT (content/…):` →
  still unresolved.

### What to keep vs delete (usual modify/delete set)

DELETE (`git rm`) — confirm the dictation / `unbloarchy-menu.jsonc`
replacement exists in the merged tree before each:
- `bin/omarchy-voxtype-install`, `bin/omarchy-voxtype-status`
- `default/hypr/bindings/voxtype.lua`
- `install/user/first-run/install-voxtype.hook`
- `test/shell.d/voxtype-invitation-test.sh` and similar voxtype-only tests
- `default/omarchy/omarchy-menu.jsonc` — ASK the user whether any new upstream
  entries should be ported into `default/unbloarchy/unbloarchy-menu.jsonc`
  before deleting the old path.

KEEP (`git add`):
- `shell/plugins/bar/indicators/Dictation.qml`
- `default/bash/fns/agent-accounts`
- `default/hypr/apps/windows-vm.lua`

Any modify/delete NOT in this list: ASK the user.

### Content conflicts

- Generated `bin/omarchy-*` shims (second line is the generator marker): do
  NOT hand-merge. `git checkout --theirs -- <file> && git add <file>`; the set
  is regenerated in step 4.
- Real `bin/omarchy-*` sources (no marker): `git mv <file> unbloarchy-<…>` and
  resolve at the new path.
- Everything else: edit out `<<<<<<<`/`=======`/`>>>>>>>` (use the
  `||||||| base` region); prefer fugitive `:Gdiffsplit!` (edit MIDDLE window,
  `d2o`/`d3o`, `:Gwrite`) or `git mergetool`.

Rules of thumb, in priority order:
1. Keep Unbloarchy naming for anything user-facing.
2. KEEP literally `omarchy`: `/usr/share/omarchy`, `/usr/share/omarchy-iso`,
   `/usr/share/omarchy-nvim`, `/usr/share/fonts/omarchy`, `/etc/omarchy.conf`,
   `/etc/omarchy-*.env`, `/var/lib/omarchy`, `/var/log/omarchy-install.log`,
   the pacman `[omarchy]` repo section, `omarchy.org`, `omacom/omarchy`,
   `omarchyplugins`, `omarchy_linux`.
3. Take theirs (upstream) for genuinely new upstream-only content the fork has
   no divergence on — the sweep rebrands it later.
4. Upstream `voxtype` → fork `dictation` renames: mirror the rename with
   `git mv`, don't keep both.

When a content conflict is genuinely ambiguous (real feature changes), ASK the
user which way to resolve it. After each file: `git add`/`git rm`.

When `git diff --name-only --diff-filter=U` is empty: verify no markers
(`grep -rn '^<<<<<<< \|^>>>>>>> ' . | head`). Then go straight to the sweep
(step 4) — do NOT commit the merge yet.

The sweep diffs the worktree against the fork's `HEAD`; committing the merge
first would make the tree match that commit and leave the sweep nothing to do.
If a later commit reports "unmerged files", resolution was incomplete.

## 4. Rebrand, regenerate shims, verify (before committing)

Run the sweep on the resolved-but-uncommitted worktree:

```bash
python3 ../sweep.py --dry
```

Show the file count, the `rename-needed:` section, and a few sample diffs to the
user; ask whether to apply. If yes: `python3 ../sweep.py`. It prints a
`rename-needed:` section listing tracked paths still named `omarchy` that do not
exist at the fork's `HEAD` — each needs a `git mv` to its `unbloarchy` name (or a
justified `git rm`/compat-list addition). Never continue with it non-empty.

If any real `bin/omarchy-*` sources remain (no generator marker), `git mv` them
to `unbloarchy-*` first. Then regenerate the shims so the compat names exist for
the tests, and run the gates:

```bash
bash install/helpers/generate-compat-shims.sh
bash test/shell.d/rebrand-integrity-test.sh   # must print "ok"
bash test/shell.d/compat-shims-test.sh        # must print "ok"
```

`rebrand-integrity-test.sh` fails on merge-new `omarchy`-named files and on
references whose `unbloarchy` twin now exists. Fix anything it reports (or
justify a compat-list addition).

Commit in two steps so history stays auditable. The first commit records the raw
resolution from the staged index; the second records the sweep, the regenerated
shims, and any hand-fixes:

```bash
git commit --no-verify
git add -A
git commit --no-verify -m "Apply targeted rebrand sweep to merge-introduced content"
git status
```

Message for the merge commit: `Sync with upstream omacom/omarchy:quattro (<UP>)`
with a body explaining the resolution intent.

## 5. Push and open the PR

```bash
git push origin sync/upstream-$UP
git push origin sync/upstream-$UP:quattro   # only if the user wants to fast-forward main
```

ASK the user which they want before pushing: push only the branch, or also
fast-forward `quattro` (only if `origin/quattro` is an ancestor of HEAD —
confirm first). Then open the PR with `gh` and share the URL.

## 6. Clean up

If worktree was used:
```bash
git worktree remove <path>
```
If in-place, offer to `git switch quattro`.

## Interaction rules

- Ask (question tool) on every ambiguous decision; never silently take a
  destructive action.
- Never `git reset --hard` / `git merge --abort` / force-push without
  confirming.
- Never push or update a shared branch without confirming.
- End with a summary: branch, commit hashes (merge + sweep + shims), kept vs
  deleted files, and the resulting ahead/behind vs `upstream/quattro`.