# CodeSuture

> Runtime Python bytecode patcher. Catches crashes, synthesizes guards, rewrites functions in-memory, and persists fixes across runs.

## What it does

CodeSuture intercepts runtime exceptions in your Python program, analyzes the failing bytecode to determine the root cause, synthesizes a deterministic guard (such as a null check or bounds clamp), rewrites the function's bytecode in memory, rewinds execution to retry, and persists the fix so it loads instantly on subsequent runs. No source files are modified. It is a surgical debugging tool that turns crashes into self-healing code.

## Quick start

```bash
pip install codesuture
```

```bash
codesuture run your_buggy_script.py
```

```
[CodeSuture] Caught AttributeError: 'NoneType' object has no attribute 'bio'
[CodeSuture] Applying null_guard on 'profile' ...
[CodeSuture] Patch applied to get_bio().
[CodeSuture] Re-executing after 1 patch(es)...

Session summary:
  Patches applied: 1
```

## How it works

1. **Catch** — A `sys.settrace` callback intercepts exceptions at the exact frame and instruction offset where they occur.
2. **Analyze** — The pattern matcher disassembles the function's bytecode, identifies the failing variable/operation, and selects the appropriate guard type.
3. **Patch** — The guard synthesizer injects new bytecode instructions (null checks, bounds clamps, safe `.get()` calls) into the function's code object. A semantic diff gate rejects patches that change too many instructions.
4. **Rewind** — Execution restarts from the top of the patched function. The guard prevents the same crash from recurring.
5. **Persist** — The patched code object is serialized to `.codesuture_store/` with JSON metadata. On subsequent runs, persisted patches load before the first function call.

## Supported guard types

| Guard type | Triggers on | Example |
|---|---|---|
| `null_guard` | `AttributeError` on `None` | `user.profile.bio` when `profile is None` |
| `index_guard` | `IndexError` (list out of range) | `items[10]` when `len(items) == 2` |
| `key_guard` | `KeyError` | `cfg["timeout"]` when key missing |
| `type_coercion_guard` | `TypeError` (conversion failure) | `int("not_a_number")` |
| `subscript_guard` | `TypeError` subscripting `None` | `data["key"]` when `data is None` |
| `chain_subscript_guard` | Nested subscript on `None` | `data["user"]["name"]` |
| `division_guard` | `ZeroDivisionError` | `x / count` when `count == 0` |
| `str_coerce_guard` | `TypeError` (str + non-str) | `"age: " + 25` |
| `file_guard` | `FileNotFoundError` | `open(path)` when file missing |
| `callable_guard` | `TypeError` calling `None` | `func()` when `func is None` |

## CLI reference

| Command | Flags | What it does |
|---|---|---|
| `codesuture run <script>` | | Run script with live patching enabled |
| `codesuture run <script>` | `--verbose` | Show patch diffs and instruction deltas |
| `codesuture run <script>` | `--shadow` | Warn if patched functions return sentinel values |
| `codesuture run <script>` | `--dry-run` | Show what would be patched without applying |
| `codesuture run <script>` | `--ttl DAYS` | Set patch expiry (default: 7 days) |
| `codesuture run <script>` | `--retries N` | Max re-execution attempts (default: 3) |
| `codesuture audit` | | Show all active patches in a formatted table |
| `codesuture rollback <name>` | | Remove persisted patch for one function |
| `codesuture rollback` | `--all` | Remove ALL patches + fingerprint registry |
| `codesuture rollback` | `--dry-run` | List what would be removed |

## Dark upgrades

- **D1 — Semantic diff safety gate**: Rejects patches that modify too many instructions, preventing runaway bytecode corruption.
- **D2 — Caller-aware patch propagation**: Propagates patches to closures and bound methods via `gc.get_referrers`.
- **D3 — Shadow execution mode**: Monitors patched function return values and warns when sentinel defaults leak downstream.
- **D4 — Patch expiry TTL**: Warns when patches exceed their time-to-live, nudging developers to fix the root cause in source.
- **D5 — Bytecode fingerprint registry**: Caches crash patterns by bytecode hash for instant guard selection on repeated failures.
- **D6 — Audit command**: Displays all active patches in a formatted table with function name, guard type, age, and rollback hints.

## Limitations

- **Python 3.11+ only** — CodeSuture relies on `PUSH_NULL`, `PRECALL`, and `POP_JUMP_FORWARD_IF_*` opcodes introduced in CPython 3.11.
- **Async not yet supported** — `async def` functions and coroutines are not patched.
- **Semantic bugs not patchable** — CodeSuture fixes structural crashes (null access, missing keys, type mismatches). It cannot fix logic errors where the code runs but produces wrong results.
- **Single-process scope** — Patches are applied per-process. Multi-process or distributed systems need separate CodeSuture instances.

## License

MIT License. See [LICENSE](LICENSE) for details.
