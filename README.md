# CodeSuture

> Runtime Python bytecode patcher. Catches crashes, synthesizes guards, rewrites functions in-memory, and persists fixes across runs.

---

## What it does

CodeSuture sits between your Python program and its crashes. When an exception occurs, it intercepts the failing frame, disassembles the bytecode to identify the root cause, injects a deterministic guard directly into the function's code object, and retries execution — all without touching a single source file.

The fix persists. On subsequent runs, CodeSuture loads the patched bytecode before the first function call. The crash is gone until you choose to remove the patch.

It is a surgical tool for keeping programs running when structural failures — null access, missing keys, type mismatches, out-of-bounds reads — would otherwise bring them down.

---

## Installation

```bash
pip install codesuture
```

Python 3.11+ required.

---

## Quick start

```bash
codesuture run your_script.py
```

```
[CodeSuture] Caught AttributeError: 'NoneType' object has no attribute 'bio'
[CodeSuture] Applying null_guard on 'profile' ...
[CodeSuture] Patch applied to get_bio().
[CodeSuture] Re-executing after 1 patch(es)...

Session summary:
  Patches applied: 1
```

Run it again:

```
[CodeSuture] Already healed, skipping: loaded persistent patch for get_bio
[CodeSuture] Session summary:
  Patches applied: 0
```

---

## How it works

1. **Catch** — A `sys.settrace` callback intercepts exceptions at the exact frame and bytecode offset where they occur.
2. **Analyze** — The pattern matcher disassembles the function's bytecode, walks the instruction chain, and identifies the failing variable or operation.
3. **Patch** — The guard synthesizer injects new bytecode instructions into the function's code object in memory. A semantic diff gate rejects patches that would change too much of the function's logic.
4. **Rewind** — Execution restarts from the patched function. The guard prevents the crash from recurring.
5. **Persist** — The patched code object is serialized to `.codesuture_store/` with JSON metadata. On subsequent runs it loads before execution begins.

No source files are modified at any point.

---

## Supported guard types

| Guard type | Triggers on | Example |
|---|---|---|
| `null_guard` | `AttributeError` on `None` | `user.profile.bio` when `profile` is `None` |
| `index_guard` | `IndexError` | `items[10]` when `len(items) == 2` |
| `key_guard` | `KeyError` | `cfg["timeout"]` when key is missing |
| `subscript_guard` | `TypeError` subscripting `None` | `data["key"]` when `data` is `None` |
| `chain_subscript_guard` | Nested subscript on `None` | `data["user"]["name"]` |
| `type_coercion_guard` | `TypeError` on conversion | `int("not_a_number")` |
| `division_guard` | `ZeroDivisionError` | `x / count` when `count == 0` |
| `str_coerce_guard` | `TypeError` on string concat | `"age: " + 25` |
| `file_guard` | `FileNotFoundError` | `open(path)` when file is missing |
| `callable_guard` | `TypeError` calling `None` | `func()` when `func` is `None` |

---

## CLI reference

| Command | Flags | What it does |
|---|---|---|
| `codesuture run <script>` | | Run script with live patching enabled |
| `codesuture run <script>` | `--verbose` | Show patch diffs and instruction deltas |
| `codesuture run <script>` | `--shadow` | Warn when patched functions return sentinel values |
| `codesuture run <script>` | `--dry-run` | Preview what would be patched without applying |
| `codesuture run <script>` | `--ttl DAYS` | Set patch expiry in days (default: 7) |
| `codesuture run <script>` | `--retries N` | Max re-execution attempts per crash (default: 3) |
| `codesuture watch <script>` | `--max-restarts N` | Run continuously, restart after each patch |
| `codesuture audit` | | Show all active patches in a formatted table |
| `codesuture explain` | | Human-readable breakdown of what each patch changed |
| `codesuture explain <name>` | | Explain one function's patch |
| `codesuture rollback <name>` | | Remove one persisted patch |
| `codesuture rollback` | `--all` | Remove all patches and the fingerprint registry |
| `codesuture rollback` | `--dry-run` | Preview what would be removed |

---

## Runtime Intelligence

Beyond basic patching, CodeSuture includes a set of higher-order behaviors that make it safe to use in real codebases:

**Semantic diff gate** — Patches that would modify too many instructions relative to the guard type are automatically rejected. The engine will never corrupt a complex function to patch a simple crash.

**Caller-aware propagation** — After patching a function, CodeSuture uses `gc.get_referrers` to find every live reference to the original code object — closures, bound methods, partials — and updates them all. No in-memory copy of the broken function survives.

**Shadow execution mode** — `--shadow` monitors the return value of patched functions. If a sentinel default (`""`, `0`, `None`) leaks into downstream logic, CodeSuture logs a warning before it causes a second failure.

**Patch expiry** — Every persisted patch carries a configurable TTL. When a patch ages past its limit, CodeSuture logs a reminder that the underlying bug should be addressed in source code. Patches are scaffolding, not permanent fixes.

**Bytecode fingerprint registry** — Crash sites are hashed by their surrounding instruction window. When the same crash pattern appears again, CodeSuture applies the known guard directly without re-running analysis.

**Audit trail** — `codesuture audit` displays every active patch: function name, guard type, target variable, default value, age, and rollback instructions. `codesuture explain` gives a plain-language breakdown of exactly what each patch changed and whether the default value is safe for downstream consumers.

---

## What CodeSuture is not

**Not a logger.** It does not record exceptions and move on. It patches the function and retries.

**Not a fuzzer or static analyzer.** It operates at runtime on live bytecode, not on source.

**Not autonomous.** Patches should be reviewed via `codesuture audit` and `codesuture explain`. The goal is to keep your program running while you address the root cause — not to replace the fix.

---

## Limitations

**Python 3.11+ only.** CodeSuture depends on bytecode structures introduced in CPython 3.11. Earlier versions are not supported.

**List and dict comprehensions are not patchable.** Comprehensions are implemented as anonymous nested code objects in CPython. CodeSuture detects crashes inside them and logs a warning, but does not attempt to patch them. Refactor the comprehension into a named function to enable patching.

**Semantic bugs are not patchable.** CodeSuture fixes structural crashes — null access, missing keys, type mismatches, bounds errors. It cannot fix logic errors where the code runs but produces wrong results.

**Single-process scope.** Patches apply per-process. Multi-process applications need a CodeSuture instance per worker. The `.codesuture_store/` directory is shared on disk, so patches load correctly on restart.

**Async support is experimental.** `async def` functions with standard `CO_COROUTINE` frames are patched. Async generators and deeply nested `await` chains may not be handled correctly in all cases.

---

## License

MIT. See [LICENSE](LICENSE) for details.