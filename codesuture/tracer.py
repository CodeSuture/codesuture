import sys
import os
import json
from datetime import datetime
from codesuture.pattern_matcher import analyze_exception
from codesuture.guard_synthesizer import synthesize_guarded_code
from codesuture.code_replacer import replace_function_code, get_function_from_frame
from codesuture.rewind import rewind_frame_to_start

_PYTHON_PREFIX = os.path.normcase(os.path.abspath(sys.prefix)) + os.sep
_PYTHON_BASE_PREFIX = os.path.normcase(os.path.abspath(sys.base_prefix)) + os.sep

def _is_internal_frame(frame):

    co_filename = frame.f_code.co_filename

    if co_filename.startswith('<'):
        return True

    try:
        norm = os.path.normcase(os.path.abspath(co_filename))
        if norm.startswith(_PYTHON_PREFIX) or norm.startswith(_PYTHON_BASE_PREFIX):
            return True
    except (ValueError, OSError):
        pass
    return False

class CodeSutureTracer:
    def __init__(self, dry_run=False, log_file=None, max_retries=3, autonomous=False, script_path=None, verbose=False, shadow=False, ttl=7):
        self.dry_run = dry_run
        self.log_file = log_file
        self.max_retries = max_retries
        self.autonomous = autonomous
        self.script_path = script_path
        self.verbose = verbose
        self.shadow_mode = shadow
        self.ttl = ttl
        self._patched_codes = {}  
        self.attempts = {}  
        self.stats = {
            "patched": 0,
            "dry_run_suggestions": 0,
            "self_healed": 0
        }
        self.patched_signatures = {}  
        self._handled_exc_ids = set()  

    def __call__(self, frame, event, arg):
        if event == 'return' and self.shadow_mode and frame.f_code in self._patched_codes:
            from codesuture.shadow import shadow_check
            func_name = frame.f_code.co_name
            guard_type = self._patched_codes[frame.f_code]
            shadow_check(func_name, arg, guard_type)
            return self

        if event == 'exception':
            exc_type, exc_value, exc_tb = arg
            self._handle_exception(frame, exc_type, exc_value, exc_tb)
            return self
        return self

    def _extract_crash_key(self, exc_type, exc_value):

        import re
        if exc_type.__name__ == 'KeyError':
            return str(exc_value).strip("'\"")
        elif exc_type.__name__ == 'AttributeError':
            m = re.search(r"has no attribute '(\w+)'", str(exc_value))
            if m:
                return m.group(1)
        elif exc_type.__name__ == 'TypeError':
            m = re.search(r"'NoneType' object is not subscriptable", str(exc_value))
            if m:
                return '__subscript__'
        return None

    def _handle_exception(self, frame, exc_type, exc_value, exc_tb, thread=None):

        if _is_internal_frame(frame):
            return

        name = getattr(frame.f_code, 'co_qualname', '') or frame.f_code.co_name
        if '<listcomp>' in name or '<genexpr>' in name or \
           '<dictcomp>' in name or '<setcomp>' in name:
            import logging
            logging.getLogger(__name__).debug(
                "[CodeSuture] Skipping %s — "
                "comprehensions are not patchable via __code__", name
            )
            return

        from codesuture.persistence import HEALED_FUNCTIONS, _heal_key
        from codesuture.code_replacer import get_function_from_frame
        try:
            func = get_function_from_frame(frame)
            if func is not None:
                func_name = getattr(func, '__qualname__', func.__name__)
                module_name = getattr(func, '__module__', '__main__')
                crash_key = self._extract_crash_key(exc_type, exc_value)
                if _heal_key(module_name, func_name, crash_key) in HEALED_FUNCTIONS:
                    return
        except Exception:
            pass

        exc_id = id(exc_value)
        if exc_id in self._handled_exc_ids:
            return

        spec = None
        from codesuture.fingerprint import compute_fingerprint, lookup, record
        fp = compute_fingerprint(frame.f_code, frame.f_lasti, exc_type.__name__)
        cached = lookup(fp)
        if cached:
            print(f"[CodeSuture] Known crash pattern #{fp[:8]} -- "
                  f"applying cached {cached['guard_type']} guard directly.")
            from codesuture.pattern_matcher import PatchSpec

            spec = PatchSpec(
                strategy=cached['guard_type'],
                var_name=cached['target'],
                default_value=cached.get('default_value', None),
                key_name=tuple(cached.get('key_name')) if isinstance(cached.get('key_name'), list) else cached.get('key_name', None)
            )

        if spec is None:
            try:
                spec = analyze_exception(frame, exc_type, exc_value, exc_tb)
            except Exception as internal_exc:

                spec = self._self_heal(internal_exc)
                if spec is None:
                    return

                try:
                    spec = analyze_exception(frame, exc_type, exc_value, exc_tb)
                except Exception:
                    return

        if spec is None:

            from codesuture.pattern_matcher import check_learned_rules
            func = get_function_from_frame(frame)
            if func is not None:
                func_name = getattr(func, '__qualname__', func.__name__)
                spec = check_learned_rules(func_name, exc_type.__name__, str(exc_value))

        if spec is None and self.autonomous and func is not None:

            print(f"[CodeSuture] Autonomous mode activated for unknown error: {exc_type.__name__}")
            import traceback
            from codesuture.code_replacer import get_source_from_frame
            from codesuture.plugins.autonomous import propose_fix
            from codesuture.sandbox import test_fix
            from codesuture.knowledge import save_learned_rule
            from codesuture.pattern_matcher import PatchSpec

            tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            function_source = get_source_from_frame(frame)

            new_source = propose_fix(tb_text, function_source, exc_type.__name__, str(exc_value))

            module_name = getattr(func, '__module__', '__main__')

            if test_fix(self.script_path, module_name, func_name, new_source, exc_type.__name__):
                print(f"[CodeSuture] LLM fix PASSED sandbox. Learning rule for {func_name}.")
                save_learned_rule(exc_type.__name__, str(exc_value), func_name, new_source)
                spec = PatchSpec(
                    strategy='autonomous_rule',
                    var_name=func_name,
                    default_value=new_source
                )
            else:
                print("[CodeSuture] LLM fix FAILED sandbox. Skipping autonomous patch.")

        if spec is None:
            return

        key = (id(frame.f_code), frame.f_lasti)
        tries = self.attempts.get(key, 0)
        if tries >= self.max_retries:
            print(f"[CodeSuture] Max retries ({self.max_retries}) reached at "
                  f"{frame.f_code.co_name}:{frame.f_lineno}, giving up.")
            return

        self.attempts[key] = tries + 1

        _thread_name = thread.name if thread is not None else None

        entry = {
            "timestamp": datetime.now().isoformat(),
            "function": frame.f_code.co_name,
            "filename": frame.f_code.co_filename,
            "lineno": frame.f_lineno,
            "exception": f"{exc_type.__name__}: {exc_value}",
            "strategy": spec.strategy,
            "var_name": spec.var_name,
            "default": repr(spec.default_value),
        }
        if _thread_name is not None:
            entry["thread"] = _thread_name

        display_name = spec.var_name
        if spec.key_name:
            display_name = spec.key_name[-1] if isinstance(spec.key_name, tuple) else spec.key_name
        elif spec.strategy == 'null_guard' and exc_type.__name__ == 'AttributeError':
            import re
            m = re.search(r"has no attribute '(\w+)'", str(exc_value))
            if m:
                display_name = m.group(1)

        if self.dry_run:
            entry["action"] = "dry_run"
            from codesuture.fingerprint import lookup as fp_lookup
            fp_hit = fp_lookup(fp) if fp else None
            if fp_hit:
                try:
                    import os as _os
                    fp_file = ".codesuture_fingerprints"
                    if _os.path.isfile(fp_file):
                        with open(fp_file, "r", encoding="utf-8") as fpf:
                            fp_data = json.load(fpf)
                        count = fp_data.get(fp, {}).get("count", 1) if isinstance(fp_data.get(fp), dict) else 1
                    else:
                        count = 0
                except Exception:
                    count = 0
            else:
                count = 0
            if count >= 3:
                confidence = "HIGH"
            elif count >= 1:
                confidence = "MEDIUM"
            else:
                confidence = "LOW"
            confidence_detail = (f"pattern seen {count}x in fingerprint registry" if count > 0
                                 else "new pattern, not in fingerprint registry")
            print(f"[CodeSuture DRY-RUN] Would apply {spec.strategy} on '{display_name}' in {frame.f_code.co_name}()")
            print(f"[CodeSuture DRY-RUN] Confidence: {confidence} ({confidence_detail})")
            print(f"  Default value: {repr(spec.default_value)}")
            print(f"  Guard type: {spec.strategy}")
            self._log(entry)
            self.stats["dry_run_suggestions"] += 1
            return
        else:
            print(f"[CodeSuture] Caught {exc_type.__name__}: {exc_value}")

            sig = (spec.var_name, spec.key_name, spec.strategy, exc_type.__name__)
            is_reuse = sig in self.patched_signatures

            if is_reuse:
                print(f"[CodeSuture] Reusing existing patch for '{display_name}' in {frame.f_code.co_name}()")
                spec = self.patched_signatures[sig]

            if not cached:
                print(f"[CodeSuture] Applying {spec.strategy} on '{display_name}' ...")

            try:
                if getattr(spec, 'target_func', None):
                    func = spec.target_func
                    old_code = getattr(func, '__code__', frame.f_code)
                else:
                    func = get_function_from_frame(frame)
                    old_code = frame.f_code

                new_bc = synthesize_guarded_code(old_code, spec)
                new_code = new_bc.to_code()
                self._persist_patch(frame, old_code, new_code, func)

                replace_function_code(func, new_code)

                if getattr(spec, 'target_func', None):
                    assert spec.target_func.__code__ is new_code, "Property fget code replacement failed"

                from codesuture.persistence import save_patch
                save_patch(func, new_code, spec, self.ttl)

                if self.shadow_mode:
                    self._patched_codes[new_code] = spec.strategy

                if self.verbose:
                    from codesuture.diff_guard import semantic_diff
                    diff = semantic_diff(old_code, new_code, spec.strategy)
                    print(f"[CodeSuture DEBUG] Diff: +{diff.added} -{diff.removed} instructions (allowed <= {diff.allowed})")

                if not is_reuse:
                    self.patched_signatures[sig] = spec

                if not cached:
                    record(fp, spec.strategy, spec.var_name, getattr(func, '__name__', 'unknown'), exc_type.__name__, spec.default_value, spec.key_name)

                entry["action"] = "applied"
                self._log(entry)
                self.stats["patched"] += 1
                self._handled_exc_ids.add(exc_id)
                print(f"[CodeSuture] Patch applied to {getattr(func, '__name__', 'unknown')}().")
                return
            except Exception as e:
                from codesuture.guard_synthesizer import PatchValidationError, PatchRejectedError
                if isinstance(e, PatchValidationError):
                    print(f"[CodeSuture] {e}")
                    entry["action"] = "rejected"
                elif isinstance(e, PatchRejectedError):
                    entry["action"] = "rejected"
                elif isinstance(e, RuntimeError) and old_code.co_flags & 0x100:
                    print(f"[CodeSuture] WARNING: async patch for {old_code.co_name}() "
                          f"raised RuntimeError: {e} -- aborting patch, not persisting.")
                    entry["action"] = "aborted"
                else:
                    import traceback as _tb
                    _tb.print_exc()
                    print(f"[CodeSuture] Patch failed: {e}")
                    entry["action"] = "failed"

                entry["error"] = str(e)
                self._log(entry)
                return

    def _self_heal(self, internal_exc):

        import traceback as tb_mod
        internal_tb = sys.exc_info()[2]
        if internal_tb is None:
            return None
        curr = internal_tb
        while curr.tb_next:
            curr = curr.tb_next
        internal_frame = curr.tb_frame

        print(f"[CodeSuture] ENGINE SELF-HEAL: caught internal {type(internal_exc).__name__}: {internal_exc}")
        print(f"[CodeSuture]   in {internal_frame.f_code.co_name}() at {internal_frame.f_code.co_filename}:{internal_frame.f_lineno}")

        try:
            spec = analyze_exception(
                internal_frame, type(internal_exc), internal_exc, internal_tb
            )
        except Exception:
            print("[CodeSuture]   self-heal analysis failed")
            return None

        if spec is None:
            print("[CodeSuture]   no deterministic patch found for internal error")
            return None

        print(f"[CodeSuture]   Applying {spec.strategy} on '{spec.var_name}' …")
        try:
            func = get_function_from_frame(internal_frame)
            new_bc = synthesize_guarded_code(internal_frame.f_code, spec)
            new_code = new_bc.to_code()
            replace_function_code(func, new_code)
            self.stats["patched"] += 1
            print(f"[CodeSuture]   Self-healed {func.__name__}().")

            from codesuture.persistence import save_patch
            save_patch(func, new_code)

            return spec
        except Exception as e:
            print(f"[CodeSuture]   self-heal patch failed: {e}")
            return None

    def _persist_patch(self, frame, old_code, new_code, func=None):
        import gc
        import ctypes
        replaced = False
        propagated_count = 0

        refs = gc.get_referrers(old_code)
        for ref in refs:
            if hasattr(ref, "__code__") and getattr(ref, "__code__", None) is old_code:
                try:
                    ref.__code__ = new_code
                    replaced = True
                    propagated_count += 1
                except Exception:
                    pass
            elif hasattr(ref, "__func__"):
                fn = getattr(ref, "__func__", None)
                if hasattr(fn, "__code__") and getattr(fn, "__code__", None) is old_code:
                    try:
                        fn.__code__ = new_code
                        replaced = True
                        propagated_count += 1
                    except Exception:
                        pass
            elif isinstance(ref, tuple):
                for i, c in enumerate(ref):
                    if c is old_code:
                        try:
                            addr = id(ref) + 24 + i * 8
                            ctypes.c_void_p.from_address(addr).value = id(new_code)
                            ctypes.pythonapi.Py_IncRef(ctypes.py_object(new_code))
                            replaced = True
                        except Exception:
                            pass

        if propagated_count > 0:
            print(f"[CodeSuture] Propagated patch to {propagated_count} additional live reference(s) of {frame.f_code.co_name}.")
        elif replaced:
            print(f"[CodeSuture] In-memory propagated patch applied to {frame.f_code.co_name}.")
        else:
            if func is None:
                func_name = frame.f_code.co_name
                func = frame.f_globals.get(func_name)

            if func and hasattr(func, "__code__") and getattr(func, "__code__", None) is old_code:
                func.__code__ = new_code
                print(f"[CodeSuture] In-memory propagated patch applied to {func.__name__}().")
            else:
                print("[CodeSuture] Could not find code object in memory to persist.")

    def _log(self, entry):
        if self.log_file:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                json.dump(entry, f, default=str)
                f.write('\n')

    def report(self):
        print("\n[CodeSuture] Session summary:")
        print(f"  Patches applied: {len(self.patched_signatures)}")
        if self.dry_run:
            print(f"  Dry-run suggestions: {self.stats['dry_run_suggestions']}")
            print(f"[CodeSuture DRY-RUN] No patches applied. Run without --dry-run to apply.")

_original_excepthook = None

def _codesuture_excepthook(tracer, exc_type, exc_value, exc_tb):
    import threading
    if exc_tb:
        tracer._handle_exception(exc_tb.tb_frame, exc_type, exc_value, exc_tb, thread=threading.current_thread())

    if _original_excepthook:
        _original_excepthook(exc_type, exc_value, exc_tb)
    else:
        sys.__excepthook__(exc_type, exc_value, exc_tb)

def install(dry_run=False, log_file=None, max_retries=3, autonomous=False, script_path=None, verbose=False, shadow=False, ttl=7):
    global _original_excepthook
    import threading
    tracer = CodeSutureTracer(dry_run, log_file, max_retries, autonomous, script_path, verbose, shadow, ttl)
    sys.settrace(tracer)
    threading.settrace(tracer)

    if getattr(threading, 'excepthook', None) is not None:
        if threading.excepthook != getattr(threading, '__excepthook__', None):
             _original_excepthook = threading.excepthook
        threading.excepthook = lambda args: _codesuture_excepthook(tracer, args.exc_type, args.exc_value, args.exc_traceback)

    return tracer

def uninstall():
    global _original_excepthook
    sys.settrace(None)
    import threading
    threading.settrace(None)
    if getattr(threading, 'excepthook', None) is not None:
        threading.excepthook = _original_excepthook or getattr(threading, '__excepthook__', sys.__excepthook__)
        _original_excepthook = None