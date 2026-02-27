def get_entry_node_tools() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "build_soft_knowledge_root",
                "description": "Build root node for soft knowledge graph",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concepts": {"type": "array", "items": {"type": "string"}},
                        "reasoning_pattern": {"type": "string"},
                    },
                    "required": [
                        "concepts",
                        "reasoning_pattern",
                    ],
                },
            },
        }
    ]
