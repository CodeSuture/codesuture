import os

def get_age():
    user = None
    return user["age"]

def calc_discount(price):
    discount = 0
    return price / discount

def get_config():
    conf = {'theme': 'dark'}
    return conf['font_size']

def get_item(lst, i):
    return lst[i]

def greet(name, age):
    return "Hello " + name + ", age: " + age

def read_data(filename):
    with open(filename) as f:
        return f.read()

def test_pattern(name, func, *args):
    print(f"\n--- Testing {name} ---")
    try:
        print(f"Attempt 1: {func(*args)}")
    except Exception as e:
        print(f"Attempt 1 failed: {e}")
    
    try:
        print(f"Attempt 2: {func(*args)}")
    except Exception as e:
        print(f"Attempt 2 failed: {e}")

def main():
    test_pattern("Subscript Guard", get_age)
    test_pattern("Division Guard", calc_discount, 100)
    test_pattern("KeyError Guard", get_config)
    test_pattern("IndexError Guard", get_item, [1, 2, 3], 10)
    test_pattern("StrConcat Guard", greet, "Alice", 30)
    test_pattern("File Guard", read_data, "missing_file_123.txt")

if __name__ == "__main__":
    main()
