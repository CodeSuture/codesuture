
import os
import json
import shutil
from datetime import datetime

from codesuture.persistence import CACHE_DIR

def rollback_function(name):

    if not os.path.isdir(CACHE_DIR):
        print("[CodeSuture] Nothing to roll back.")
        return

    removed = 0
    for fname in list(os.listdir(CACHE_DIR)):

        base = fname.rsplit(".", 1)[0]  
        func_part = base.split(".", 1)[-1] if "." in base else base

        if func_part == name or base == name or func_part.endswith(name):
            path = os.path.join(CACHE_DIR, fname)
            os.remove(path)
            removed += 1

    if removed > 0:
        print(f"[CodeSuture] Rolled back patch for '{name}'. "
              f"Run your script again to re-patch if needed.")
    else:
        print(f"[CodeSuture] No patch found matching '{name}'.")

def rollback_all():

    count = 0
    if os.path.isdir(CACHE_DIR):
        count = len(os.listdir(CACHE_DIR))
        if count == 0:
            print("[CodeSuture] Nothing to roll back.")
            return
        shutil.rmtree(CACHE_DIR)
    else:
        print("[CodeSuture] Nothing to roll back.")
        return

    fp = ".codesuture_fingerprints"
    if os.path.isfile(fp):
        os.remove(fp)

    print(f"[CodeSuture] Cleared {count} patch file(s) and fingerprint registry.")

def rollback_dry_run():

    if not os.path.isdir(CACHE_DIR):
        print("[CodeSuture] Nothing to roll back. Store does not exist.")
        return

    json_files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".json")]
    if not json_files:
        print("[CodeSuture] Nothing to roll back. No patches found.")
        return

    now = datetime.utcnow()
    print()
    print("  [CodeSuture DRY-RUN] Would remove the following patches:")
    print()
    for jf in json_files:
        path = os.path.join(CACHE_DIR, jf)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            func = data.get("func_name", "?")
            guard = data.get("guard_type", "?")
            age = "?"
            if "patched_at" in data:
                dt = datetime.fromisoformat(data["patched_at"])
                age = f"{(now - dt).days}d"
            print(f"    - {func}  guard={guard}  age={age}")
        except Exception:
            print(f"    - {jf}  (could not read metadata)")

    fp = ".codesuture_fingerprints"
    if os.path.isfile(fp):
        print(f"    - .codesuture_fingerprints (fingerprint registry)")
    print()
    print("  Run 'codesuture rollback --all' to actually remove them.")