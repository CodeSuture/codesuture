import os
import json

KNOWLEDGE_DIR = ".codesuture_knowledge"
KNOWLEDGE_FILE = os.path.join(KNOWLEDGE_DIR, "learned_rules.json")

def load_learned_rules():
    if not os.path.exists(KNOWLEDGE_FILE):
        return []
    try:
        with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_learned_rule(exc_type_name, exc_message, func_name, new_source):
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    rules = load_learned_rules()

    for rule in rules:
        if rule["func_name"] == func_name and rule["exc_type_name"] == exc_type_name:

            rule["new_source"] = new_source
            rule["exc_message"] = exc_message
            break
    else:
        rules.append({
            "func_name": func_name,
            "exc_type_name": exc_type_name,
            "exc_message": exc_message,
            "new_source": new_source
        })

    with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)