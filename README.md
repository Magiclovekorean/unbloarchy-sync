# Syncing Unbloarchy with upstream Omarchy

How to pull in new upstream commits, resolve the conflicts, rebrand the
merge-introduced content, and push the result.

There are opencode commands that automate parts of this. They live in the
`.opencode/command/` folder next to this guide and read the same rules:

- `/unbloarchy-sync` — runs the full procedure below end to end: picks the tip,
  creates the sync branch, merges, resolves the conflicts, sweeps, regenerates
  the shims, pushes, and opens the PR. It asks you before any ambiguous or
  destructive decision.
- `/unbloarchy-resolve-merge-conflicts` — does only step 3: resolves the
  conflicted files against the keep/delete rules below, stages them, and stops
  when `git diff --name-only --diff-filter=U` is empty. Use it when you handle
  fetch/branch/merge (and everything after) yourself.

They are shortcuts around the manual steps below, not a different procedure.

## Remotes: `origin` vs `upstream`

These are just names; you can call them anything.

| Remote     | Points at                              | Access     |
|------------|----------------------------------------|------------|
| `origin`   | `github.com:Magiclovekorean/unbloarchy`| read/write (your fork) |
| `upstream` | `github.com:omacom/omarchy`            | read (source project)  |

You **fetch** from `upstream` and **push** to `origin`.


## One-time setup

From your local clone of the fork at `../unbloarchy`:

```bash
git remote add upstream git@github.com:omacom/omarchy.git   # if missing
git fetch upstream
```

This repo contains the guide and helper scripts, but the actual work is done in
`../unbloarchy`. From that repo root, call the tools as
`../unbloarchy-sync/sweep.py` and `../unbloarchy-sync/transform.py`.

`transform.py` decides which `omarchy` tokens may be rebranded and which are
protected. It resolves its ground-truth repo from `--repo`, the
`UNBLOARCHY_REPO` env var, or the git repo containing the current directory.
`sweep.py` applies the transform only to lines changed by a merge; it runs with
`--work` (default: current directory), `--repo` (default: same as `--work`), and
`--dry`.

**Order matters:** the sweep runs AFTER the conflicts are resolved but BEFORE
the merge is committed. It diffs the worktree against your fork's `HEAD` and
rewrites only the lines the merge introduced; once the merge is committed the
tree matches that commit and the sweep would find nothing. It is a rebranding
tool, not a conflict resolver — running it on an unresolved merge corrupts the
working tree.

## Per-sync procedure

### 1. Pick a fresh upstream tip and create a sync branch

```bash
git fetch upstream quattro
UP=$(git rev-parse --short upstream/quattro)
```

Then create the sync branch. Two ways — pick one:

**Option A — in place (simplest, one folder):**

```bash
git switch -c sync/upstream-$UP quattro
```

Your current folder switches onto the new branch. Create a branch from your
fork's base (`quattro`) and check it out, all in your normal clone.

**Option B — separate worktree (optional, isolates the merge):**

```bash
git worktree add -b sync/upstream-$UP ../unbloarchy-sync-merge quattro
cd ../unbloarchy-sync-merge
```

- `git worktree add` — creates an **additional working directory** linked to the
  same repository (shared history/objects, separate checked-out files).
- `-b sync/upstream-$UP` — creates and checks out a **new branch** named after
  the upstream tip.
- `../unbloarchy-sync-merge` — the directory for this new working tree.
- `quattro` — the **base commit** the new branch starts from.

Both options create the same branch; the only difference is *where* it's
checked out.

Why choose the worktree: your main clone stays on `quattro`, untouched, so you
can keep building/comparing while the merge sits half-resolved in the separate
folder. A branch can only be checked out in one place, so if you want `quattro`
and the sync branch live at the same time, you **must** use a worktree.

Why skip it: one folder, no extra directory, no cleanup. Fine if you don't need
`quattro` checked out during the merge. If you choose Option B, clean up later
with `git worktree remove ../unbloarchy-sync-merge`.

### 2. Merge upstream

```bash
git merge upstream/quattro
```

Expect conflicts in docs, tests, `applications.lua`, renamed `bin/` scripts,
etc.

### 3. Resolve conflicts — do NOT skip this

A merge will almost always leave real conflicts, even when git prints
`Resolved '<file>' using previous resolution.`. That message is `rerere`
replaying old choices for some files; it is **not** the same as all conflicts
being resolved. Files with genuinely changed lines — and every modify/delete
case — stay unmerged.

You can hand this step to `/unbloarchy-resolve-merge-conflicts`, which applies
the rules below to the files currently left unmerged and asks you when a
decision isn't covered.

**You are not done until this is empty:**

```bash
git diff --name-only --diff-filter=U
```

See the full conflict list with `git status`. Three shapes to expect:

- **Content conflict** (`UU` / `AA`): the file contains `<<<<<<<`, `=======`,
  `>>>>>>>` markers. Edit it down to a single correct version, delete the
  marker lines, then `git add <file>`.
- **Modify/delete** (`DU` / `UD`): one side deleted the file, the other edited
  it. No markers — just decide: `git add <file>` to keep, or `git rm <file>`
  to delete.
- **Both added** (`AA`): two different new files at the same path — merge by
  hand.

Take a whole side quickly instead of editing:

```bash
git checkout --ours   <file>   # keep YOUR branch's version
git checkout --theirs <file>   # take UPSTREAM's version
git add <file>
```

Resolving with Neovim + fugitive:

```vim
:Git status          " cursor on a conflicted file
:Gdiffsplit!         " 3-way: left=ours, middle=working, right=theirs
" edit the MIDDLE window; ]c / [c jump, d2o = take ours, d3o = take theirs
:Gwrite              " save + stage (git add)
```

In `:Gstatus`, `2X` / `3X` take `--ours` / `--theirs` for the whole file
during a merge.

Recommended: show the common ancestor inside the markers so conflicts are far
easier to judge:

```bash
git config merge.conflictstyle zdiff3
```

This repo's special cases:

- **Generated `bin/omarchy-*` shims** (their second line is
  `# Generated by generate-compat-shims.sh; do not edit.`): do not hand-merge.
  Take either side, then regenerate everything with
  `bash install/helpers/generate-compat-shims.sh` afterwards.
- **Real `bin/omarchy-*` sources** (no generator marker): `git mv` them to the
  `unbloarchy-*` name and resolve at the new path.
- **`bin/unbloarchy-*` and everything else** (docs, configs, tests, `shell/`):
  resolve normally.

Resolution rules of thumb:

- **Keep Unbloarchy naming** for anything user-facing: `unbloarchy-*` bin
  scripts, skill directories, docs.
- **Keep these tokens literally `omarchy`** (do not rebrand):
  - package/system paths: `/usr/share/omarchy`, `/usr/share/omarchy-iso`,
    `/usr/share/omarchy-nvim`, `/usr/share/fonts/omarchy`
  - config paths: `/etc/omarchy.conf`, `/etc/omarchy-*.env`
  - the pacman repo section `[omarchy]`
  - org/repo strings: `omarchy.org`, `omacom/omarchy`, `omarchyplugins`
- **Take theirs (upstream)** for genuinely new upstream-only content where your
  fork has no divergence (new docs, new `applications.lua` entries, new
  features) — then let the sweep rebrand it.
- Handle renames specially (e.g. upstream `voxtype` → your `dictation` naming).

### Reading the merge output (what each line means)

The torrent of merge lines is easy to misread. Translate each kind:

- `Auto-merging <path>` — git merged it cleanly. Done, nothing to do.
- `Resolved '<path>' using previous resolution.` — **rerere** automatically re-applied a resolution you recorded in a previous sync; the file is already staged. Usually fine, but it is not a substitute for review — check `git diff --cached` on the important ones.
- `Recorded preimage for '<path>'` — rerere saw a conflict but had no stored resolution to apply. **The file is still unresolved.**
- `CONFLICT (content): Merge conflict in <path>` — the file contains `<<<<<<<` / `=======` / `>>>>>>>` markers. Resolve by hand, then `git add`.
- `CONFLICT (modify/delete): <path>` — one side deleted the file, the other edited it. No markers; pick keep (`git add`) or delete (`git rm`).
- `Automatic merge failed; fix conflicts and then commit the result.` — expected; it means step 3 is not finished, not that anything broke.

`Recorded preimage` and `CONFLICT (modify/delete)` lines are the files you must still touch.

### What to keep vs delete (this repo's usual modify/delete set)

Upstream keeps renaming voxtype → dictation and rewriting the menu. Expect these patterns:

- **Delete (`git rm`)** — upstream deleted these and the fork's direction agrees:
  - `bin/omarchy-voxtype-install`, `bin/omarchy-voxtype-status`
  - `default/hypr/bindings/voxtype.lua`
  - `install/user/first-run/install-voxtype.hook`
  - `test/shell.d/voxtype-invitation-test.sh` and similar voxtype-only tests
  - `default/omarchy/omarchy-menu.jsonc` — upstream still ships it, but the fork's menu lives at `default/unbloarchy/unbloarchy-menu.jsonc`. Delete the old path, then check whether upstream added new menu entries worth porting into the fork's menu.
- **Keep (`git add`)** — upstream deleted these but the fork still uses them:
  - `shell/plugins/bar/indicators/Dictation.qml`
  - `default/bash/fns/agent-accounts`
  - `default/hypr/apps/windows-vm.lua`

Before `git rm`-ing anything, confirm the replacement (dictation / unbloarchy-menu equivalents) actually exists in the merged tree.

Only when `git diff --name-only --diff-filter=U` is empty, run the sweep (step
4) on the resolved-but-uncommitted worktree. **Do NOT commit the merge first**:
the sweep diffs the worktree against your fork's `HEAD`, and a fresh merge
commit would leave it nothing to change. Even after the sweep, if git rejects a
commit with "Committing is not possible because you have unmerged files", the
resolution is incomplete — go back and work down the list.

### 4. Rebrand the merge-introduced content (before the merge commit)

Run the sweep from the repo root while the merge is still **uncommitted**:

```bash
python3 ./sweep.py --dry            # review what it would change
python3 ./sweep.py                  # apply
git diff --name-only | wc -l
```

`sweep.py` rewrites only lines that differ from your fork's `HEAD` (i.e. lines
the merge introduced) and shields the protected tokens plus quoted `omarchy`
literals. It ALSO prints a `rename-needed:` section: tracked paths that still
carry an `omarchy` name but do not exist at your fork's `HEAD`. The content
sweep can never rename files for you — every entry needs a `git mv` to its
`unbloarchy` name (or a justified `git rm`, or an addition to the compat list
in `test/shell.d/rebrand-integrity-check.py`). Never continue while
`rename-needed:` is non-empty.

The sweep is blind to *semantics*: where a rebranded line referred to the
**upstream** Omarchy project (e.g. "depends on upstream Omarchy signing"), the
sweep turns it into the wrong "upstream Unbloarchy". Skim the diff for the word
"upstream" and revert those spellings to `Omarchy`.

Now **run the tests**, but regenerate the shims first so the compat names they
check against exist in the tree:

```bash
bash install/helpers/generate-compat-shims.sh   # so compat names exist in the tree
bash test/shell.d/rebrand-integrity-test.sh     # must print "ok"
bash test/shell.d/compat-shims-test.sh          # must print "ok"
```

`rebrand-integrity-test.sh` fails on merge-new `omarchy`-named files and on
references whose `unbloarchy` twin now exists (renamed targets). It is part of
`./test/shell`, so it also guards every future sync. A failure lists concrete
`path:line` fixes — resolve them (or justify a compat-list addition) before
continuing.

### 5. After the tests: commit the sync

Do this only once both tests above print `ok`. For the whole shell suite
(including them), run:

```bash
./test/shell
```

Then commit in two steps so history stays auditable. The sweep edited the
worktree only, so the first commit records the raw conflict resolution and the
second records the rebrand, the regenerated shims, and any hand-fixes:

```bash
git diff --stat                    # (optional) what is about to land
git commit --no-verify             # 1) merge commit: the resolved (pre-sweep) index
git add -A                         # 2) stage the swept worktree + regenerated shims
git commit --no-verify -m "Apply targeted rebrand sweep to merge-introduced content"
git status                         # should report a clean tree
```

Suggested merge-commit message (edit to taste):

```
Sync with upstream omacom/omarchy:quattro (<tip>)

Merge upstream changes into Unbloarchy fork. Resolve conflicts by
preserving Unbloarchy-specific paths, compat layer, and naming.
```

Now continue to push (step 6).

### 6. Push and integrate

```bash
git push origin sync/upstream-$UP
```

Then either open the PR GitHub prints, or fast-forward your main branch:

```bash
git push origin sync/upstream-$UP:quattro
```

### 7. Clean up

If you chose the in-place branch (Option A), switch back to your main branch
when done:

```bash
git switch quattro
```

If you chose the worktree (Option B), remove it:

```bash
cd /path/to/your/clone
git worktree remove ../unbloarchy-sync-merge
```

## Troubleshooting

**Oops — I ran the sweep (or anything else) before resolving.** Abort and
restart; nothing was committed, so nothing is lost:

```bash
git merge --abort              # discards the merge AND working-tree edits
git merge upstream/quattro     # rerere re-applies previous resolutions
```

**`bin/omarchy-*` shims look inconsistent after the merge.** They are generated
output, not source. Do not edit them by hand — reconcile the whole set:

```bash
bash install/helpers/generate-compat-shims.sh
```

This creates missing wrappers, removes stale ones that carry the generator
marker, and adds the legacy default-path aliases. It refuses to overwrite
unmanaged files and aborts on a conflict — resolve that before proceeding.
Then review and commit the regenerated `bin/omarchy*` files as a separate
commit, per the repo convention ("include the resulting `bin/omarchy*`
wrappers in the change").

## Sanity checks

Before committing, make sure no conflict markers remain:

```bash
grep -rn '^<<<<<<< \|^>>>>>>> ' . | head
```

After regenerating shims, verify the compat wrapping still holds:

```bash
test/shell.d/compat-shims-test.sh
```

After the sweep (and after regenerating shims), verify no `omarchy` name or
reference was left dangling by the rebrand:

```bash
test/shell.d/rebrand-integrity-test.sh     # must print "ok"
```

It fails on merge-new `omarchy`-named files — the sweep never renames files —
and on references whose `unbloarchy` twin now exists in the tree. It is part of
`./test/shell`, so it runs with every sync and every future commit automatically.

If `transform.py` needs updating as upstream evolves, regenerate it from the
new `HEAD`: it protects tokens that appear as `omarchy` more often than
`unbloarchy` in your branch.

