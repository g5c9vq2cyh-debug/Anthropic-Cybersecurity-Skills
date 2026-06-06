# `.ci/` — script lint gate

The `lint-scripts` workflow runs three checks over every script in
`skills/` and `tools/`:

1. **`py_compile`** on every `.py` — any syntax error fails CI.
2. **Ruff bug-class** (`F821` undefined name, `F823` use-before-assign,
   `F402` import shadowed by loop var) — hard fail, no baseline. These
   are runtime bugs.
3. **Ruff cleanup ratchet** (`F401` unused import, `F541` empty f-string,
   `F841` unused local) — compared to `.ci/ruff-baseline.txt`. New
   findings fail; existing ones are grandfathered.

## When CI fails on the ratchet

You added (or moved into a file) a new `F401`/`F541`/`F841` instance.
Either fix it (preferred) or, if accepted, refresh the baseline:

```sh
python3 .ci/check-ruff-baseline.py --write
```

Then commit the updated `.ci/ruff-baseline.txt`.

## Baseline format

One line per `(file, code)` key, sorted:

```
skills/<skill>/scripts/agent.py:F401 3
```

Tracks **counts per file**, not line numbers — so unrelated edits that
shift lines won't trigger CI noise.
