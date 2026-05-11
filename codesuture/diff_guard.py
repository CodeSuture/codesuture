import dis
from dataclasses import dataclass

@dataclass
class DiffResult:
    guard_type: str
    added: int
    removed: int
    changed: int
    allowed: int
    rejected: bool
    reason: str = ""

def semantic_diff(original_code, patched_code, guard_type: str) -> DiffResult:
    orig_ops  = [(i.opname, i.argval) for i in dis.get_instructions(original_code)]
    patch_ops = [(i.opname, i.argval) for i in dis.get_instructions(patched_code)]
    added   = len([x for x in patch_ops if x not in orig_ops])
    removed = len([x for x in orig_ops  if x not in patch_ops])
    changed = max(added, removed)
    allowed = max(50, int(len(orig_ops) * 0.40))
    rejected = changed > allowed
    reason = (
        f"Semantic diff too large for {guard_type}: "
        f"{changed} instructions changed, allowed <= {allowed}. "
        f"Patch was NOT applied."
    ) if rejected else ""
    return DiffResult(guard_type, added, removed, changed, allowed, rejected, reason)
