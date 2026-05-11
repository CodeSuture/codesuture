import debugpy

def enable(port=5678):
    debugpy.listen(port)
    print(f"[CodeSuture] Waiting for debugger on port {port}...")
    debugpy.wait_for_client()
    print("[CodeSuture] Debugger attached. Live patching active.")