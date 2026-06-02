#!/usr/bin/env python3
"""Scrub Azure secrets and tenant-identifying values from Jupyter notebook OUTPUTS.

Tutorial notebooks in this repo keep their cell outputs (they aid learning). This
redacts the sensitive bits in place while leaving the pedagogical content (agent
replies, charts, model/region names, HTTP status codes) intact. Cell SOURCE is never
modified; image outputs are left untouched.

Follows the repo's CONTRIBUTING.md "Notebook output hygiene" convention:
  - KEEP deterministic resource-name suffixes (e.g. this repo's `c2676f`, `n5d3ja`) and
    the resource names that embed them - they are the canonical, consistent demo values.
  - Map sensitive UUIDs (subscription id, tenant id, Entra principal / managed-identity /
    instance-identity ids) to the all-zeros placeholder `00000000-0000-0000-0000-000000000000`
    (allowlisted). Public role-definition GUIDs that appear in cell SOURCE are kept.
  - Replace the subscription name, signed-in UPN, keys/tokens, and session/correlation
    ids with curly-brace placeholders.
  Keep: sha256 image digests; public role-definition GUIDs.

Usage:
  scrub_notebooks.py NB [NB ...]          # scrub in place (prints what changed)
  scrub_notebooks.py --check NB [NB ...]  # exit 1 if a known secret remains (no modify)
"""
import json
import pathlib
import re
import subprocess
import sys

ALLZERO = "00000000-0000-0000-0000-000000000000"

GUID = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
JWT = re.compile(r'eyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]*')
SESS = re.compile(r'\b(?=[A-Za-z0-9]{40,})(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])[A-Za-z0-9]{40,}\b')
UPN = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+\.onmicrosoft\.com')
ACCTKEY = re.compile(r'AccountKey=[A-Za-z0-9+/=]+')
SAS = re.compile(r'sig=[A-Za-z0-9%]+')
BEARER = re.compile(r'(?i)bearer\s+[A-Za-z0-9._\-]{12,}')


def az_account():
    try:
        r = subprocess.run(["az", "account", "show", "-o", "json"],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return {}


def env_secrets():
    vals = set()
    p = pathlib.Path(".env")
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            k, _, v = line.partition("=")
            if v.strip() and re.search(r'KEY|SECRET|TOKEN|PASSWORD|SAS', k, re.I):
                vals.add(v.strip())
    return vals


def build_context(nb):
    a = az_account()
    return {
        "sub": a.get("id"),
        "ten": a.get("tenantId"),
        "name": a.get("name"),
        "upn": (a.get("user") or {}).get("name"),
        "secrets": env_secrets(),
        "src_guids": {g.lower() for c in nb["cells"] if c["cell_type"] == "code"
                      for g in GUID.findall("".join(c["source"]))},
    }


def scrub_text(s, ctx):
    if not isinstance(s, str):
        return s
    for sec in sorted(ctx["secrets"], key=len, reverse=True):
        s = s.replace(sec, "{api-key}")
    s = JWT.sub("{token}", s)
    s = BEARER.sub("Bearer {token}", s)
    if ctx["name"]:
        s = s.replace(ctx["name"], "{subscription-name}")
    # Sensitive UUIDs -> the canonical all-zeros placeholder. Public role-definition
    # GUIDs that appear in cell SOURCE are kept. Deterministic resource-name suffixes
    # (e.g. c2676f) are NOT touched - per CONTRIBUTING.md they are the canonical demo
    # suffix, kept for consistency across the notebook set.
    s = GUID.sub(lambda m: m.group(0) if m.group(0).lower() in ctx["src_guids"] else ALLZERO, s)
    s = SESS.sub("{session-id}", s)
    s = UPN.sub("{user}@{tenant}.onmicrosoft.com", s)
    s = ACCTKEY.sub("AccountKey={redacted}", s)
    s = SAS.sub("sig={redacted}", s)
    return s


def scrub_field(v, ctx):
    if isinstance(v, str):
        return scrub_text(v, ctx)
    if isinstance(v, list):
        return [scrub_field(x, ctx) for x in v]
    return v


def scrub_outputs(nb, ctx):
    for c in nb["cells"]:
        if c["cell_type"] != "code":
            continue
        for o in c.get("outputs", []):
            for fld in ("text", "evalue", "ename"):
                if fld in o:
                    o[fld] = scrub_field(o[fld], ctx)
            if "traceback" in o:
                o["traceback"] = scrub_field(o["traceback"], ctx)
            for k in list(o.get("data", {})):
                if k.startswith("image"):
                    continue
                o["data"][k] = scrub_field(o["data"][k], ctx)


def residual_leaks(nb, ctx):
    blob = json.dumps(nb)
    leaks = []
    for label, val in [("subscription id", ctx["sub"]), ("tenant id", ctx["ten"]),
                       ("subscription name", ctx["name"])] + [("secret", s) for s in ctx["secrets"]]:
        if val and val in blob:
            leaks.append(label)
    return sorted(set(leaks))


def process(path, check):
    nb = json.loads(pathlib.Path(path).read_text())
    ctx = build_context(nb)
    if check:
        leaks = residual_leaks(nb, ctx)
        if leaks:
            print(f"[scrub] {path}: SENSITIVE VALUE PRESENT: {leaks}", file=sys.stderr)
            return 1
        return 0
    before = json.dumps(nb, sort_keys=True)
    scrub_outputs(nb, ctx)
    if json.dumps(nb, sort_keys=True) != before:
        with open(path, "w") as f:
            json.dump(nb, f, indent=1)
            f.write("\n")
        print(f"[scrub] {path}: redacted sensitive output values")
    else:
        print(f"[scrub] {path}: clean (no changes)")
    return 1 if residual_leaks(nb, ctx) else 0


def main():
    args = sys.argv[1:]
    check = "--check" in args
    files = [a for a in args if a != "--check"]
    if not files:
        print(__doc__)
        sys.exit(0)
    rc = 0
    for f in files:
        rc |= process(f, check)
    sys.exit(rc)


if __name__ == "__main__":
    main()
