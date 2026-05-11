import gc

def make_processor(get_user_fn):
    def process(uid):
        user = get_user_fn(uid)
        return user.name.strip()
    return process

def get_user(uid):
    return None

process = make_processor(get_user)

original_code = process.__code__
refs = gc.get_referrers(original_code)
print(f"Total refs to code: {len(refs)}")
for r in refs:
    if hasattr(r, '__code__') and r.__code__ is original_code:
        print(f"Function ref: {r}")
        if r is process:
            print("  (This is the main 'process' function)")
    else:
        print(f"Other ref: {type(r)}")
