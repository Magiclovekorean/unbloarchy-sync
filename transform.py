#!/usr/bin/env python3
"""Rebrand transform derived from the fork's current HEAD (ground truth).

A brandable maximal token is KEPT (left as `omarchy`) iff, across the fork HEAD,
its `omarchy` spelling is at least as common as its `unbloarchy` spelling
(disk dominance) -- this captures package names, package-owned paths, mirror/org
references and legacy service names.  Everything else is case-substituted.
Package-owned path prefixes and pacman repo literals are always kept.

The fork repo used as ground truth is resolved from, in order:
  --repo / configure(repo=...), the UNBLOARCHY_REPO environment variable, or the
git repository containing the current directory.
"""
import argparse
import collections
import os
import re
import subprocess

_TOK_RE = re.compile(r"[A-Za-z0-9_.~/$@:{}()\-]*omarchy[A-Za-z0-9_.~/$@:{}()\-]*", re.I)
_BARE = {"omarchy", "omarchy.", "omarchy-", "omarchy)"}

# always-kept package/system path prefixes (matched against a maximal token,
# which may start mid-path when preceded by a quote, `=`, or whitespace, so the
# leading slash is optional: (?:^|/) anchors at the token start or at any path
# separator inside the run)
_PREFIX_KEEP = [re.compile(p) for p in (
    r"(?:^|/)usr/share/omarchy-iso",
    r"(?:^|/)usr/share/omarchy-nvim",
    r"(?:^|/)usr/share/omarchy(?![-\w])",
    r"(?:^|/)etc/omarchy\.conf",
    r"(?:^|/)etc/omarchy-dell-haptic-touchpad\.env",
    r"(?:^|/)var/lib/omarchy",
    r"(?:^|/)var/log/omarchy-install\.log",
    r"omarchy_linux",
    r"default/fonts/omarchy(?![-\w])",
    r"(?:^|/)usr/share/fonts/omarchy(?![-\w])",
)]

# always-kept substrings (org / repos / mirrors)
_SUBSTR_KEEP = ("omarchy.org", "omacom/omarchy", "omarchyplugins")

# literal 'omarchy' / "omarchy" strings and the [omarchy] pacman repo section
# name (package query, pacman.conf header, escaped-bracket sed/awk references)
_LITERAL_BARE = re.compile(r"""(["'])omarchy\1|\\?\[omarchy\\?\]""")

# populated by configure()
REPO = None
PROTECTED = None


def default_repo():
    env = os.environ.get("UNBLOARCHY_REPO")
    if env:
        return os.path.abspath(env)
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    return os.getcwd()


def case_replace_segment(s):
    return (s.replace("OMARCHY", "\x00")
             .replace("Omarchy", "\x01")
             .replace("omarchy", "\x02")
             .replace("\x00", "UNBLOARCHY")
             .replace("\x01", "Unbloarchy")
             .replace("\x02", "unbloarchy"))


def _grep_tokens(repo, pattern, rev="HEAD"):
    r = subprocess.run(["git", "-C", repo, "grep", "-hoiE", pattern, rev],
                       capture_output=True, text=True)
    return collections.Counter(l.strip().lower() for l in r.stdout.splitlines())


def build_protected_tokens(repo):
    head_o = _grep_tokens(repo, _TOK_RE.pattern)
    head_u = _grep_tokens(repo, _TOK_RE.pattern.replace("omarchy", "unbloarchy"))
    toks = set()
    for t, c in head_o.items():
        if t in _BARE:
            continue
        u = case_replace_segment(t).lower()
        if u == t:
            continue
        if c >= head_u.get(u, 0):
            toks.add(t)
    return toks


def configure(repo=None):
    """Set the ground-truth fork repo and (re)build the protected token set."""
    global REPO, PROTECTED
    REPO = os.path.abspath(repo) if repo else default_repo()
    PROTECTED = build_protected_tokens(REPO)
    return REPO


def _keep_token(full_lower):
    if any(k in full_lower for k in _SUBSTR_KEEP):
        return True
    for rx in _PREFIX_KEEP:
        if rx.search(full_lower):
            return True
    if full_lower in PROTECTED:
        return True
    return False


def transform_line(line):
    if "omarchy" not in line.lower():
        return line
    if PROTECTED is None:
        configure()
    # shield quoted bare 'omarchy' literals and the [omarchy] pacman repo section
    spans = []

    def _shield(m):
        spans.append(m.group(0))
        return f"\x03{len(spans)-1}\x03"

    line = _LITERAL_BARE.sub(_shield, line)
    out = []
    pos = 0
    for m in _TOK_RE.finditer(line):
        out.append(line[pos:m.start()])
        tok = m.group(0)
        # a maximal run may merge several brandable pieces; decide on whole run
        if _keep_token(tok.lower()):
            out.append(tok)
        else:
            out.append(case_replace_segment(tok))
        pos = m.end()
    out.append(line[pos:])
    result = "".join(out)
    return re.sub(r"\x03(\d+)\x03", lambda m: spans[int(m.group(1))], result)


def _validate(repo, old, new):
    ns = subprocess.run(["git", "-C", repo, "show", "--name-status", "-M", "--format=", new],
                        capture_output=True, text=True).stdout

    def lines(rev, path):
        r = subprocess.run(["git", "-C", repo, "show", f"{rev}:{path}"], capture_output=True)
        if r.returncode != 0:
            return None
        return r.stdout.decode("utf-8", "surrogateescape").split("\n")

    total = ok = 0
    for line in ns.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        st = parts[0]
        if st.startswith(("R", "C")):
            oldp, newp = parts[1], parts[2]
        elif st.startswith("M"):
            oldp = newp = parts[1]
        else:
            continue
        o = lines(old, oldp)
        n = lines(new, newp)
        if o is None or n is None or len(o) != len(n):
            continue
        for a, b in zip(o, n):
            if a == b:
                if re.search("omarchy", a, re.I):
                    total += 1
                    ok += int(transform_line(a) == a)
            else:
                total += 1
                ok += int(transform_line(a) == b)
    if total:
        print(f"validate: {ok}/{total} ({100*ok/total:.2f}%)")
    else:
        print("validate: no comparable lines")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Rebrand transform / validation.")
    ap.add_argument("--repo", default=None,
                    help="ground-truth fork repo (default: UNBLOARCHY_REPO or cwd's git repo)")
    ap.add_argument("--old", help="old revision to validate the transform against")
    ap.add_argument("--new", help="new revision to validate the transform against")
    args = ap.parse_args()

    repo = configure(args.repo)
    if args.old and args.new:
        _validate(repo, args.old, args.new)
    else:
        print(f"repo: {repo}")
    print(f"protected tokens: {len(PROTECTED)}")
