import types
import inspect

def replace_function_code(func, new_code):

    from codesuture.guard_synthesizer import propagate_patch
    propagate_patch(func, new_code)

def get_function_from_frame(frame):
    name = frame.f_code.co_name
    code = frame.f_code

    if name in frame.f_locals:
        candidate = frame.f_locals[name]
        if hasattr(candidate, '__code__') and candidate.__code__ is code:
            return candidate

    if name in frame.f_globals:
        candidate = frame.f_globals[name]
        if hasattr(candidate, '__code__') and candidate.__code__ is code:
            return candidate

    if name == '<module>':
        return None

    self_obj = frame.f_locals.get('self')
    if self_obj is not None:
        cls = type(self_obj)
        method = getattr(cls, name, None)
        if method is not None:
            if isinstance(method, property) and method.fget is not None:
                func = method.fget
            else:
                func = method
            if hasattr(func, '__func__'):
                func = func.__func__
            if hasattr(func, '__code__') and func.__code__ is code:
                return func

    cls_obj = frame.f_locals.get('cls')
    if cls_obj is not None and isinstance(cls_obj, type):
        method = getattr(cls_obj, name, None)
        if method is not None:
            if isinstance(method, property) and method.fget is not None:
                func = method.fget
            else:
                func = method
            if hasattr(func, '__func__'):
                func = func.__func__
            if hasattr(func, '__code__') and func.__code__ is code:
                return func

    for val in frame.f_globals.values():
        if isinstance(val, type):
            method = getattr(val, name, None)
            if method is not None:
                if isinstance(method, property) and method.fget is not None:
                    func = method.fget
                else:
                    func = method
                if hasattr(func, '__func__'):
                    func = func.__func__
                if hasattr(func, '__code__') and func.__code__ is code:
                    return func

    for val in frame.f_globals.values():
        if hasattr(val, '__wrapped__'):
            inner = val.__wrapped__
            if hasattr(inner, '__code__') and inner.__code__ is code:
                return inner
        if hasattr(val, '__code__') and val.__code__ is code:
            return val

    return None

def get_source_from_frame(frame):

    func = get_function_from_frame(frame)
    try:
        return inspect.getsource(func)
    except Exception as e:
        return f"# Could not get source: {e}\n"