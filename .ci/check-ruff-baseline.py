#!/usr/bin/env python3
"""Ratchet-style baseline gate for ruff findings.

Runs ``ruff check --select=$CODES`` over ``skills`` and ``tools``, aggregates
findings per ``(file, code)``, and compares to ``.ci/ruff-baseline.txt``.

Fails CI when any ``(file, code)`` count exceeds the baseline, or when a new
``(file, code)`` key appears. Decreases and removals are allowed (and shown as
"ratchet wins" the baseline can be regenerated to capture). The baseline file is
human-readable: one ``<path>:<code> <count>`` line per key, sorted.
"""
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = REPO_ROOT / ".ci" / "ruff-baseline.txt"
CODES = "F401,F541,F841"
TARGETS = ["skills", "tools"]


def current_counts() -> Counter:
    proc = subprocess.run(
        ["ruff", "check", f"--select={CODES}", "--no-cache",
         "--output-format=json", *TARGETS],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if proc.returncode not in (0, 1):
        sys.stderr.write(proc.stderr)
        sys.exit(proc.returncode)
    findings = json.loads(proc.stdout) if proc.stdout.strip() else []
    counts: Counter = Counter()
    for f in findings:
        path = Path(f["filename"]).resolve().relative_to(REPO_ROOT).as_posix()
        counts[(path, f["code"])] += 1
    return counts


def load_baseline() -> Counter:
    counts: Counter = Counter()
    if not BASELINE.exists():
        return counts
    for line in BASELINE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, count = line.rpartition(" ")
        path, _, code = key.rpartition(":")
        counts[(path, code)] = int(count)
    return counts


def format_baseline(counts: Counter) -> str:
    lines = [f"{path}:{code} {count}"
             for (path, code), count in sorted(counts.items())]
    return "\n".join(lines) + ("\n" if lines else "")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--write":
        counts = current_counts()
        BASELINE.write_text(format_baseline(counts))
        print(f"Wrote {len(counts)} (file, code) entries to {BASELINE.relative_to(REPO_ROOT)}")
        return 0

    current = current_counts()
    baseline = load_baseline()

    regressions = []
    for key, count in current.items():
        if count > baseline.get(key, 0):
            regressions.append((key, baseline.get(key, 0), count))

    improvements = sum(
        1 for key, count in baseline.items() if current.get(key, 0) < count
    )

    if regressions:
        print("FAIL: new ruff findings beyond baseline:")
        for (path, code), old, new in sorted(regressions):
            delta = "new" if old == 0 else f"{old} -> {new}"
            print(f"  {path}: {code} ({delta})")
        print(
            f"\nFix the new findings, or run "
            f"`python .ci/check-ruff-baseline.py --write` to accept them."
        )
        return 1

    print(f"OK: {sum(current.values())} ruff findings, all within baseline.")
    if improvements:
        print(
            f"Note: {improvements} baseline entries have improved. "
            f"Consider regenerating the baseline."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
