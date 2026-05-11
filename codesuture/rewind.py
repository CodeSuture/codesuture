"""
codesuture/rewind.py
Lowâ€‘level frame manipulation using ctypes.
"""
import ctypes
import sys

class PyObject(ctypes.Structure):
    _fields_ = [
        ("ob_refcnt", ctypes.c_ssize_t),
        ("ob_type", ctypes.c_void_p),
    ]

class PyVarObject(PyObject):
    _fields_ = [
        ("ob_size", ctypes.c_ssize_t),
    ]

class PyFrameObject(PyVarObject):

    _fields_ = [
        ("f_back", ctypes.c_void_p),
        ("f_code", ctypes.c_void_p),
        ("f_builtins", ctypes.c_void_p),
        ("f_globals", ctypes.c_void_p),
        ("f_locals", ctypes.c_void_p),
        ("f_valuestack", ctypes.c_void_p),
        ("f_stacktop", ctypes.c_void_p),
        ("f_lasti", ctypes.c_int),
        ("f_lineno", ctypes.c_int),

    ]

def _cast_frame(frame):

    return ctypes.cast(id(frame), ctypes.POINTER(PyFrameObject))

def rewind_frame_to_start(frame, code):

    cf = _cast_frame(frame)

    cf.contents.f_lasti = -1
    cf.contents.f_lineno = code.co_firstlineno