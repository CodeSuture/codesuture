import subprocess
import sys
import shutil
import os

def clear_cache():
    if os.path.exists('.codesuture_store'):
        shutil.rmtree('.codesuture_store')

def test_e2e_harness2():
    clear_cache()
    result = subprocess.run(
        [sys.executable, '-m', 'codesuture.cli', 'run', 'tests/test_harness2.py'],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    stdout = result.stdout or ""
    assert "Patch applied" in stdout, f"stdout: {stdout}\nstderr: {result.stderr}"
    assert result.returncode == 0

def test_e2e_original_harness():
    clear_cache()
    result = subprocess.run(
        [sys.executable, '-m', 'codesuture.cli', 'run', 'tests/test_harness.py'],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    stdout = result.stdout or ""
    assert "Patch applied" in stdout, f"stdout: {stdout}\nstderr: {result.stderr}"
    assert "Patches applied: 2" in stdout
    assert result.returncode == 0

def test_persisted_main_patches_apply_before_first_call():
    clear_cache()
    first = subprocess.run(
        [sys.executable, '-m', 'codesuture.cli', 'run', 'tests/test_harness.py', '--self-test'],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    assert first.returncode == 0
    stdout1 = first.stdout or ""
    assert "Patch applied to get_user_name()." in stdout1, f"stdout: {stdout1}\nstderr: {first.stderr}"
    assert "Patch applied to calc_discount()." in stdout1, f"stdout: {stdout1}\nstderr: {first.stderr}"

    second = subprocess.run(
        [sys.executable, '-m', 'codesuture.cli', 'run', 'tests/test_harness.py', '--self-test'],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    assert second.returncode == 0
    stdout2 = second.stdout or ""
    assert "Already healed, skipping: loaded persistent patch for __main__.get_user_name" in stdout2
    assert "Already healed, skipping: loaded persistent patch for __main__.calc_discount" in stdout2
    assert "Patches applied: 0" in stdout2, f"stdout: {stdout2}\nstderr: {second.stderr}"
    assert "Caught" not in stdout2
