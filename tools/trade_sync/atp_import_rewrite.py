#!/usr/bin/env python3
"""scripts/atp_import_rewrite.py — owner order M65 X-3 / X-5: copy the engine's PORT set from a Trade source tree into a checkout of the
PRIVATE repo atp-private, under `atp_private/trade_engine/<original module path>`, with the code unmodified EXCEPT its import paths
(this mechanical rewrite, so a re-sync for a new tag is one command: scripts/export_to_atp_private.sh <tag>).

What is copied (from `--src`, a clean export of the tagged commit — never the working tree):
  • every module the live engine imports that scripts/engine_closure.py classifies PORT (+ the packages' __init__.py and data files);
  • the tests that cover them: tests/test_*.py whose own imports (and those of the tests/ helpers they import) are all PORT modules
    (+ those helpers, conftest.py, __init__.py), so they can run inside atp-private;
  • docs/knowledge/ (KB, method, owner's notes, Method Pack, PA standard) at its own relative path, so the code finds it as in Trade;
  • scripts/build_method_pack.py (the pack builder), this script and export_to_atp_private.sh (tools/trade_sync/), a README.
Never copied: data files outside the packages, secrets (.env, *.db, tokens), VPS paths, trade-data. The copy of `atp_private/trade_engine/`
is replaced as a whole (it is a generated mirror of one tag); nothing else in the checkout is touched.

The rewrite (every import of a top-level module of this repo; relative imports unchanged; line numbers kept):
  import X                ⇒ import atp_private.trade_engine.X as X   (a missing module raises ModuleNotFoundError, as before)
  import X as Y           ⇒ import atp_private.trade_engine.X as Y
  import X.y              ⇒ import atp_private.trade_engine.X.y; import atp_private.trade_engine.X as X
  from X[.y] import …     ⇒ from atp_private.trade_engine.X[.y] import …
  in test files only: "X.y.z" string literals whose first two parts are a module of this repo (monkeypatch / mock targets)
                          ⇒ "atp_private.trade_engine.X.y.z"

    python3 scripts/atp_import_rewrite.py --src <export of the tag> --dest <atp-private checkout> --tag <tag> --commit <sha>
"""
import argparse
import ast
import io
import json
import os
import re
import shutil
import sys
import tokenize

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from scripts import engine_closure as EC                                  # noqa: E402

PREFIX = "atp_private.trade_engine"
PKG_DIR = os.path.join("atp_private", "trade_engine")
KB_DIR = os.path.join("docs", "knowledge")
TOOLS = ("scripts/atp_import_rewrite.py", "scripts/export_to_atp_private.sh", "scripts/engine_closure.py")
NEVER = re.compile(r"(^|/)(\.env[^/]*|.*\.db|.*\.sqlite3?|.*token.*\.json|.*secret.*|__pycache__(/.*)?)$", re.I)


# ------------------------------------------------------------------------------------------------ rewrite
def _imp_line(node, tops):
    """The replacement text for one `import a, b as c` statement (None ⇒ untouched)."""
    parts, changed = [], False
    for a in node.names:
        top = a.name.split(".")[0]
        if top not in tops:
            parts.append(f"import {a.name}" + (f" as {a.asname}" if a.asname else ""))
            continue
        changed = True
        if a.asname:
            parts.append(f"import {PREFIX}.{a.name} as {a.asname}")
        elif "." in a.name:
            parts.append(f"import {PREFIX}.{a.name}; import {PREFIX}.{top} as {top}")
        else:
            parts.append(f"import {PREFIX}.{a.name} as {a.name}")          # a missing module still raises ModuleNotFoundError
    return "; ".join(parts) if changed else None


def _string_target(s, root):
    """A dotted string naming a module of this repo (its first two parts resolve to a module file) ⇒ rewritten, else None."""
    if not re.fullmatch(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)+", s):
        return None
    parts = s.split(".")
    if EC.resolve(".".join(parts[:2]), root) is None:
        return None
    return f"{PREFIX}.{s}"


def _ch(line, col):
    """ast column (UTF-8 bytes) ⇒ str index (the KB text and comments are Marathi)."""
    return len(line.encode("utf-8")[:col].decode("utf-8", errors="ignore"))


def rewrite(text, tops, root, strings=False):
    """The source with its repo imports rewritten (see the module docstring); everything else byte-identical. `strings` (test files only):
    also the dotted mock / monkeypatch targets — never in engine code, whose strings may be output."""
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    edits = []                                                              # (line0, char0, line1, char1, new)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            new = _imp_line(node, tops)
            if new is not None:
                edits.append((node.lineno, _ch(lines[node.lineno - 1], node.col_offset), node.end_lineno,
                              _ch(lines[node.end_lineno - 1], node.end_col_offset), new))
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module and node.module.split(".")[0] in tops:
            line = lines[node.lineno - 1]
            c0 = _ch(line, node.col_offset)
            m = re.match(r"(from\s+)" + re.escape(node.module) + r"(\s+import\b)", line[c0:])
            if m is None:
                raise ValueError(f"cannot rewrite `from {node.module} import …` at line {node.lineno}")
            edits.append((node.lineno, c0, node.lineno, c0 + m.end(), f"{m.group(1)}{PREFIX}.{node.module}{m.group(2)}"))
    if strings:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):  # string targets ("decision3.engine.V22")
            if tok.type != tokenize.STRING:
                continue
            m = re.fullmatch(r"([rRuU]?)(['\"])(.*)\2", tok.string, flags=re.S)
            if not m:
                continue
            new = _string_target(m.group(3), root)
            if new and m.group(3).split(".")[0] in tops:
                (l0, c0), (l1, c1) = tok.start, tok.end
                edits.append((l0, c0, l1, c1, f"{m.group(1)}{m.group(2)}{new}{m.group(2)}"))
    for l0, c0, l1, c1, new in sorted(edits, reverse=True):
        a, b = lines[l0 - 1], lines[l1 - 1]
        lines[l0 - 1:l1] = [a[:c0] + new + b[c1:]]
    return "".join(lines)


# ------------------------------------------------------------------------------------------------ the PORT set
def port_set(src):
    """(modules, tests, data files) to copy, as paths relative to `src`."""
    clo = EC.closure(root=src)
    mods = {m for m in clo if EC.classify(m) == "PORT"}
    mods |= {p for p in EC.PORT_ALWAYS if os.path.exists(os.path.join(src, p))}
    for m in list(mods):                                                    # every package on the way has its __init__.py
        d = os.path.dirname(m)
        while d:
            i = os.path.join(d, "__init__.py")
            if os.path.exists(os.path.join(src, i)):
                mods.add(i)
            d = os.path.dirname(d)
    tests, helpers = set(), set()
    tdir = os.path.join(src, "tests")

    def direct(rel, seen=None):
        """The test's own imports + those of the tests/ helpers it imports (the code it reaches through PORT modules is theirs)."""
        seen = set() if seen is None else seen
        if rel in seen:
            return set()
        seen.add(rel)
        out = set(EC.imports_of(rel, src))
        for h in [x for x in out if x.startswith("tests/")]:
            out |= direct(h, seen)
        return out
    for f in sorted(os.listdir(tdir)):
        if not (f.startswith("test_") and f.endswith(".py")):
            continue
        rel = f"tests/{f}"
        try:
            deps = direct(rel) - {rel}
        except SyntaxError:
            continue
        code = {d for d in deps if not d.startswith("tests/")}
        if code and code <= mods:
            tests.add(rel)
            helpers |= {d for d in deps if d.startswith("tests/")}
    for f in sorted(os.listdir(tdir)):                                      # every tests/ helper that stays inside (conftest needs some)
        rel = f"tests/{f}"
        if f.endswith(".py") and not f.startswith("test_") and rel not in helpers:
            try:
                code = {d for d in direct(rel) if not d.startswith("tests/")}
            except SyntaxError:
                continue
            if code <= mods:
                helpers.add(rel)
    for x in ("tests/__init__.py", "tests/conftest.py"):
        if os.path.exists(os.path.join(src, x)):
            helpers.add(x)
    data = set()
    for m in mods:
        d = os.path.dirname(m)
        if not d or d == "scripts":
            continue
        for dp, sub, fs in os.walk(os.path.join(src, d)):
            sub[:] = [x for x in sub if x != "__pycache__" and not os.path.exists(os.path.join(dp, x, "__init__.py"))]
            for f in fs:
                rel = os.path.relpath(os.path.join(dp, f), src)
                if not f.endswith((".py", ".pyc")) and not NEVER.search(rel):
                    data.add(rel)
    return sorted(mods), sorted(tests | helpers), sorted(data)


def copy(src, dest, tag, commit, log=print):
    tops = EC.top_modules(src)
    mods, tests, data = port_set(src)
    pkg = os.path.join(dest, PKG_DIR)
    if os.path.isdir(pkg):
        shutil.rmtree(pkg)                                                  # the mirror of one tag, replaced as a whole
    os.makedirs(pkg)
    for d in ("atp_private",):
        init = os.path.join(dest, d, "__init__.py")
        if not os.path.exists(init):
            open(init, "w").close()
    open(os.path.join(pkg, "__init__.py"), "w").close()
    manifest = {}
    for rel in mods + tests:
        with open(os.path.join(src, rel), encoding="utf-8") as f:
            text = f.read()
        out = rewrite(text, tops, src, strings=rel.startswith("tests/"))
        p = os.path.join(pkg, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(out)
        manifest[rel] = {"rewritten": out != text}
    kb = []
    for dp, _, fs in os.walk(os.path.join(src, KB_DIR)):
        for f in fs:
            rel = os.path.relpath(os.path.join(dp, f), src)
            if not NEVER.search(rel):
                kb.append(rel)
    for rel in data + sorted(kb):
        p = os.path.join(pkg, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        shutil.copyfile(os.path.join(src, rel), p)
    tools = os.path.join(dest, "tools", "trade_sync")
    os.makedirs(tools, exist_ok=True)
    for t in TOOLS:
        if os.path.exists(os.path.join(src, t)):
            shutil.copyfile(os.path.join(src, t), os.path.join(tools, os.path.basename(t)))
    with open(os.path.join(pkg, "IMPORT_MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump({"source_repo": "abhishekwasu-hue/Trade", "tag": tag, "commit": commit, "prefix": PREFIX,
                   "modules": mods, "tests": tests, "data_files": data, "kb_files": sorted(kb),
                   "rewritten": sorted(k for k, v in manifest.items() if v["rewritten"])}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(pkg, "README.md"), "w", encoding="utf-8") as f:
        f.write(README.format(tag=tag, commit=commit, n_mod=len(mods), n_test=len(tests), n_data=len(data), n_kb=len(kb)))
    log(f"copied into {pkg}: {len(mods)} modules, {len(tests)} test files, {len(data)} data files, {len(kb)} KB files")
    return {"modules": mods, "tests": tests, "data": data, "kb": kb}


README = """# atp_private.trade_engine — Trade's engine, copied as is

Source: repository `abhishekwasu-hue/Trade`, tag `{tag}`, commit `{commit}` (owner order M65: the signal engine, chart reader, price
action, entry models and the Vision method move to ATP as is). Generated by `tools/trade_sync/export_to_atp_private.sh {tag}` — never
edit this folder by hand; a re-sync for a new tag replaces it as a whole.

- Code: {n_mod} modules at their original paths under `atp_private/trade_engine/`, unmodified except the import paths
  (`tools/trade_sync/atp_import_rewrite.py`: `import decision3` ⇒ `import atp_private.trade_engine.decision3 as decision3`, …).
- Tests: {n_test} files under `tests/` (the Trade tests whose imports stay inside this set). Run: `python -m pytest atp_private/trade_engine/tests`
  from the repository root. Tests that need the private trade-data skip without it.
- Package data: {n_data} files (e.g. `decision3/data/*.json`). KB / method / Method Pack: {n_kb} files under `docs/knowledge/` (the
  same relative path the code reads); the Method Pack builder is `scripts/build_method_pack.py`.
- Not here: market data, parity fixtures (private fixtures store on the host, `parity/{tag}/` in trade-data), secrets, VPS paths.
- ATP-GENERIC modules (Telegram, PAPER fills, exits, approvals, brokers, storage, config) are NOT copied: ATP has its own. A copied module
  that imports one of them at call time needs ATP's adapter when that path is ported (the list: Trade `docs/reader/EXPORT_MANIFEST.md`).
- PAPER only; LIVE untouched; the method code never goes into ATP's public repository.
"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="a clean export of the tagged commit (git archive)")
    ap.add_argument("--dest", required=True, help="the atp-private checkout")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--commit", required=True)
    a = ap.parse_args(argv)
    copy(os.path.abspath(a.src), os.path.abspath(a.dest), a.tag, a.commit)


if __name__ == "__main__":
    main()
