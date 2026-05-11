import os
import re

_llm = None

def get_llm():
    global _llm
    if _llm is not None:
        return _llm

    from llama_cpp import Llama
    model_path = os.environ.get("CODESUTURE_MODEL_PATH")
    if not model_path or not os.path.exists(model_path):
        raise FileNotFoundError(f"LLM model not found at {model_path}. Please download a model and set CODESUTURE_MODEL_PATH environment variable.")

    print("[CodeSuture] Loading local LLM... this may take a moment.")
    _llm = Llama(
        model_path=model_path,
        n_ctx=2048,
        verbose=False
    )
    return _llm

def propose_fix(traceback_text, function_source, exc_type_name, exc_value):
    llm = get_llm()

    prompt = f"""<|system|>
You are an expert Python developer fixing bugs autonomously.
You are given the source code of a function that crashed, and the exception traceback.
Your task is to rewrite the ENTIRE function to safely handle the exception. You MUST modify the code inside the function to fix the error. The easiest way is to wrap the failing code in a try/except block and return a fallback value (like 0 or None), or to use an if-statement to check the inputs. Do NOT return the original crashing code. Do NOT output code outside of the function.
</s>
<|user|>
The function crashed with this error:
{exc_type_name}: {exc_value}

Original Source Code:
```python
{function_source}
```

Rewrite the ENTIRE function to fix this error. Output ONLY the valid python code block.
</s>
<|assistant|>
```python
"""

    print("[CodeSuture] Asking LLM for a fix...")
    response = llm(
        prompt,
        max_tokens=512,
        stop=["```\n", "</s>"],
        temperature=0.2
    )

    output = response['choices'][0]['text']

    if "```python" in output:
        output = output.split("```python")[1]
    if "```" in output:
        output = output.split("```")[0]

    output = output.strip()
    print(f"\n[CodeSuture] LLM Proposed Fix:\n{output}\n")
    return output