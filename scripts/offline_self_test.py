import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.agentic.simulation.offline_loop import (
    deterministic_choice_question_node,
    run_offline_loop,
)


async def _stub_entry_node(state: dict[str, Any]) -> dict[str, Any]:
    root = state.get("knowledge_graph_root")
    if isinstance(root, dict) and isinstance(root.get("concepts"), list) and root.get("concepts"):
        return state
    return {
        **state,
        "knowledge_graph_root": {
            "concepts": [
                {
                    "concept": "Bias-Variance Tradeoff",
                    "familiarity": 10.0,
                    "posterior_question_count": 0,
                    "qa_history": [],
                },
                {
                    "concept": "Regularization",
                    "familiarity": 20.0,
                    "posterior_question_count": 0,
                    "qa_history": [],
                },
            ],
            "reasoning_pattern": "offline deterministic seed",
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run backend diagnosis loop without starting API services.",
    )
    parser.add_argument("--goal", default="ML interview prep")
    parser.add_argument("--user-id", default="offline-user")
    parser.add_argument("--max-round", type=int, default=5)
    parser.add_argument("--proficiency", type=float, default=60.0)
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    initial_state = {
        "question": args.goal,
        "user_id": args.user_id,
        "max_round": max(1, args.max_round),
        "question_mode": "choice",
        "choice_option_count": 4,
        "auto_answer_enabled": True,
        "auto_answer_proficiency": max(0.0, min(100.0, args.proficiency)),
    }
    result = await run_offline_loop(
        initial_state,
        entry_node_fn=_stub_entry_node,
        question_node_fn=deterministic_choice_question_node,
    )

    print(
        json.dumps(
            {
                "rounds": [
                    {
                        "round": item.round_index,
                        "concept": item.concept,
                        "score": item.score,
                        "answer": item.answer,
                    }
                    for item in result.rounds
                ],
                "final_round": int(result.state.get("current_round", 0) or 0),
                "max_round": int(result.state.get("max_round", 0) or 0),
                "final_feedback": str(result.state.get("current_feedback", "") or ""),
                "knowledge_graph_root": result.state.get("knowledge_graph_root", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(_main())
