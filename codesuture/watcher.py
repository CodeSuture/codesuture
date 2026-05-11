
import subprocess
import sys
import time

def watch(script, max_restarts=10, shadow=False, verbose=False):

    restarts = 0
    last_exception = None
    same_exception_count = 0

    print(f"[CodeSuture WATCH] Starting watch on {script} (max-restarts={max_restarts})")

    while restarts <= max_restarts:
        cmd = [sys.executable, "-m", "codesuture", "run"]
        if shadow:
            cmd.append("--shadow")
        if verbose:
            cmd.append("--verbose")
        cmd.append(script)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            print("[CodeSuture WATCH] Script timed out.")
            restarts += 1
            continue

        output = (result.stdout or "") + (result.stderr or "")
        print(output, end="")

        if result.returncode == 0:
            print("[CodeSuture WATCH] Script exited cleanly.")
            return 0

        patches_applied = output.lower().count("patch applied")

        current_exception = _extract_exception(output)
        if current_exception and current_exception == last_exception and patches_applied == 0:
            same_exception_count += 1
        else:
            same_exception_count = 0
            last_exception = current_exception

        if same_exception_count >= 2:  
            print("[CodeSuture WATCH] Unrecoverable: same exception fired 3x with 0 new patches.")
            return 1

        restarts += 1

        if restarts > max_restarts:
            break

        print(f"[CodeSuture WATCH] Restarting ({restarts}/{max_restarts})...")
        time.sleep(0.5)

    print(f"[CodeSuture WATCH] Max restarts ({max_restarts}) reached.")
    return 1

def _extract_exception(output):

    import re

    matches = re.findall(r"(?:Caught |Script exited with: )(\w+Error[:\s].*?)(?:\n|$)", output)
    if matches:
        return matches[-1].strip()

    matches = re.findall(r"(\w+Error: .+?)(?:\n|$)", output)
    if matches:
        return matches[-1].strip()
    return None