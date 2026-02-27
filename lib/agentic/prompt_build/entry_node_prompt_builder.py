from pathlib import Path

import yaml


def _read_prompt_file(filename: str) -> str:
    project_root = Path(__file__).resolve().parents[3]
    prompt_path = project_root / "lib" / "agentic" / "prompts" / filename
    raw_text = prompt_path.read_text(encoding="utf-8")
    payload = yaml.safe_load(raw_text)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid prompt yaml format: {prompt_path}")

    template = payload.get("template")
    if not isinstance(template, str) or not template.strip():
        raise ValueError(f"Missing template in prompt yaml: {prompt_path}")
    return template.strip()


def build_entry_node_prompt(question: str) -> str:
    system_template = _read_prompt_file("entry_node_system.yaml")
    user_template = _read_prompt_file("entry_node_user.yaml")

    question = (question or "").strip()
    if not question:
        question = "I am preparing for an ML algorithm engineer interview."

    # Avoid template engines here because system prompt contains JSON braces.
    user_prompt = user_template.replace("{question}", question)
    return f"{system_template}\n\n{user_prompt}"
