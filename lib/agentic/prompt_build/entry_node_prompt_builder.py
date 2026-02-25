from pathlib import Path


def _read_prompt_file(filename: str) -> str:
    project_root = Path(__file__).resolve().parents[1]
    prompt_path = project_root / "prompts" / filename
    return prompt_path.read_text(encoding="utf-8").strip()


def build_entry_node_prompt(question: str) -> str:
    system_template = _read_prompt_file("entry_node_system.md")
    user_template = _read_prompt_file("entry_node_user.md")

    question = (question or "").strip()
    if not question:
        question = "I am preparing for an ML algorithm engineer interview."

    # Avoid template engines here because system prompt contains JSON braces.
    user_prompt = user_template.replace("{question}", question)
    return f"{system_template}\n\n{user_prompt}"
