
import subprocess
import sys
import os
import textwrap
import shutil
import json

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

PASS = f"{GREEN}PASS{RESET}"
FAIL = f"{RED}FAIL{RESET}"

CRASH_TESTS = {
    "CRASH 1: Nested dict chain (3 levels deep)": {
        "script": """\
def get_merchant_address(merchant_id):
    merchants = {
        1: {"name": "Coffee Shop", "address": {"street": "123 Main", "city": "SF"}},
        2: {"name": "New Store", "address": None},
    }
    return merchants[merchant_id]["address"]["street"].upper()

print(get_merchant_address(2))
print("COMPLETED_OK")
""",
        "first_run": ["COMPLETED_OK"],
        "second_run": ["COMPLETED_OK", "already healed"],
        "must_not": ["Traceback"],
    },

    "CRASH 3: Batch with partial failures": {
        "script": """\
def process_batch(items):
    results = []
    for item in items:
        name = item["user"]["profile"]["display_name"].title()
        results.append(f"Processed: {name}")
    return results

batch = [
    {"id": 1, "user": {"profile": {"display_name": "alice"}}},
    {"id": 2, "user": {"profile": None}},
    {"id": 3, "user": {"profile": {"display_name": "bob"}}},
    {"id": 4, "user": None},
]
print(process_batch(batch))
print("COMPLETED_OK")
""",
        "first_run": ["COMPLETED_OK"],  
        "second_run": ["COMPLETED_OK", "already healed"],
        "must_not": ["Traceback"],
    },

    "CRASH 5: Thread safety (concurrent crashes)": {
        "script": """\
import threading

class SharedProcessor:
    def __init__(self):
        self.results = []

    def process(self, data):
        result = data["text"].strip().upper()
        self.results.append(result)
        return result

processor = SharedProcessor()
errors = []

def worker(data):
    try:
        return processor.process(data)
    except Exception as e:
        errors.append(str(e))

threads = [
    threading.Thread(target=worker, args=({"text": "hello"},)),
    threading.Thread(target=worker, args=(None,)),
    threading.Thread(target=worker, args=({"text": "world"},)),
]
for t in threads: t.start()
for t in threads: t.join()

print("Results:", processor.results)
print("Errors:", errors)
print("COMPLETED_OK")
""",
        "first_run": ["COMPLETED_OK"],  
        "second_run": ["COMPLETED_OK"],
        "must_not": ["Traceback"],
    },

    "CRASH 6: Recursive tree walk": {
        "script": """\
class TreeNode:
    def __init__(self, value, children=None):
        self.value = value
        self.children = children or []

def get_deepest_value(node):
    if not node.children:
        return node.value.strip()
    return get_deepest_value(node.children[0])

tree = TreeNode("root", [
    TreeNode("child", [
        TreeNode(None)
    ])
])
print(get_deepest_value(tree))
print("COMPLETED_OK")
""",
        "first_run": ["COMPLETED_OK"],
        "second_run": ["COMPLETED_OK", "already healed"],
        "must_not": ["RecursionError", "maximum recursion"],
    },

    "CRASH 8: JSON with nullable nested field": {
        "script": """\
import json

def parse_webhook(payload):
    data = json.loads(payload)
    event_type = data["event"]["type"].upper()
    user_name = data["event"]["user"]["name"]["first"].capitalize()
    return {"type": event_type, "user": user_name}

payload = json.dumps({
    "event": {
        "type": "signup",
        "user": None
    }
})
print(parse_webhook(payload))
print("COMPLETED_OK")
""",
        "first_run": ["COMPLETED_OK"],
        "second_run": ["COMPLETED_OK", "already healed"],
        "must_not": ["Traceback"],
    },

    "CRASH 9: @property with lazy load null FK": {
        "script": """\
class Order:
    def __init__(self, id, customer_id):
        self.id = id
        self._customer_id = customer_id
        self._customer_cache = None

    @property
    def customer(self):
        if self._customer_cache is None:
            customers = {1: {"name": "Alice Corp", "tier": "premium"}}
            self._customer_cache = customers.get(self._customer_id)
        return self._customer_cache

class InvoiceGenerator:
    def generate(self, order):
        name = order.customer["name"]
        tier = order.customer["tier"].upper()
        return f"Invoice for {name} ({tier})"

order = Order(id=100, customer_id=999)
print(InvoiceGenerator().generate(order))
print("COMPLETED_OK")
""",
        "first_run": ["COMPLETED_OK"],
        "second_run": ["COMPLETED_OK", "already healed"],
        "must_not": ["Traceback"],
    },
}

def run_test(name, config, workdir):

    path = os.path.join(workdir, "test_crash.py")

    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(config["script"]))

    passed = True

    r1 = subprocess.run(
        ["codesuture", "run", "test_crash.py"],
        cwd=workdir, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30
    )
    out1 = (r1.stdout or "") + (r1.stderr or "")

    for required in config["first_run"]:
        if required.lower() not in out1.lower():
            print(f"  {FAIL}  First run missing: {required}")
            passed = False

    for forbidden in config["must_not"]:
        if forbidden.lower() in out1.lower():
            print(f"  {FAIL}  First run contains: {forbidden}")
            passed = False

    if "patch applied" in out1.lower():
        print(f"  {PASS}  Patch applied on first run")
    else:
        print(f"  {FAIL}  No patch applied on first run")
        passed = False

    r2 = subprocess.run(
        ["codesuture", "run", "test_crash.py"],
        cwd=workdir, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=30
    )
    out2 = (r2.stdout or "") + (r2.stderr or "")

    for required in config["second_run"]:
        if required.lower() not in out2.lower():
            print(f"  {FAIL}  Second run missing: {required}")
            passed = False

    for forbidden in config["must_not"]:
        if forbidden.lower() in out2.lower():
            print(f"  {FAIL}  Second run contains: {forbidden}")
            passed = False

    if passed:
        print(f"  {PASS}  {name} — FULLY HEALED")

    for line in out1.splitlines():
        if any(kw in line.lower() for kw in ["patch", "guard", "crash", "error", "healed", "summary"]):
            print(f"         {DIM}{line.strip()[:120]}{RESET}")

    return passed

def clear_store(workdir):
    for name in [".codesuture_cache", ".codesuture_store", ".codesuture",
                 "codesuture_patches", ".codesuture_fingerprints"]:
        path = os.path.join(workdir, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.isfile(path):
            os.remove(path)

if __name__ == "__main__":
    workdir = os.path.dirname(os.path.abspath(__file__))

    print(f"\n{BOLD}{CYAN}CodeSuture vs Real Production Crashes{RESET}")
    print(f"{DIM}Can your engine actually heal these?{RESET}\n")

    total = 0
    passed = 0

    for name, config in CRASH_TESTS.items():
        print(f"{BOLD}{name}{RESET}")
        clear_store(workdir)

        if run_test(name, config, workdir):
            passed += 1
        total += 1
        print()

    print(f"{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}Result: {passed}/{total} crash types healed{RESET}")

    if passed == total:
        print(f"{GREEN}Your engine handles all real production crash patterns.{RESET}")
        sys.exit(0)
    else:
        failed = total - passed
        print(f"{RED}{failed} crash type(s) still kill production.{RESET}")
        print(f"{DIM}These are the ones your 129/129 didn't catch.{RESET}")
        sys.exit(1)