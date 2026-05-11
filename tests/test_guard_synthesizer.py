import pytest
import types
from codesuture.pattern_matcher import PatchSpec
from codesuture.guard_synthesizer import synthesize_guarded_code

def test_null_guard_synthesis():
    def original(x):
        return x.strip()
    spec = PatchSpec('null_guard', 'x', '')
    new_bc = synthesize_guarded_code(original.__code__, spec)
    new_code = new_bc.to_code()
    new_func = types.FunctionType(new_code, {})
    assert new_func(None) == ''
    assert new_func('hello') == 'hello'

def test_null_guard_replaces_local_none_assignment():
    def original():
        user = None
        return user.strip()

    spec = PatchSpec('null_guard', 'user', '')
    new_bc = synthesize_guarded_code(original.__code__, spec)
    new_code = new_bc.to_code()
    new_func = types.FunctionType(new_code, {})

    assert new_func() == ''

def test_division_guard_synthesis():
    def divide(price, discount):
        return price / discount
    spec = PatchSpec('division_guard', 'discount', 1)
    new_bc = synthesize_guarded_code(divide.__code__, spec)
    new_code = new_bc.to_code()
    new_func = types.FunctionType(new_code, {})
    assert new_func(100, 0) == 100.0
    assert new_func(100, 10) == 10.0
