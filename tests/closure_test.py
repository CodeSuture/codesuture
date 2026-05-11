def make_processor(get_user_fn):
    def process(uid):
        user = get_user_fn(uid)
        return user.name.strip()  
    return process

class User:
    def __init__(self, n): self.name = n

def get_user(uid):
    return None if uid != 1 else User("Alice")

if __name__ == '__main__':
    process = make_processor(get_user)
    process2 = make_processor(get_user)
    process(2)  