# Agent Graph

Current workflow is defined in `lib/agentic/graph.py`.

```text
                      +------------------+
                      |   START / input  |
                      +---------+--------+
                                |
                                v
                      +------------------+
                      |    entry_llm     |
                      | (init concepts)  |
                      +----+---------+---+
                           |         |
          if user_answer &&|         | otherwise
          current_question |         |
                           v         v
                    +-------------+  +--------------+
                    |     ref     |  |   question   |
                    | (score+upd) |  | (pick+ask)   |
                    +------+------+\ +------+-------+
                           ^        X       |
                           |       / \      v
                           |      /   \ +-----------+
                           |     /     \|auto_answer|
                           |    /       +-----+-----+
                           |   /              |
                           +--/---------------+
                               (to ref)

After `ref`:
  - if `current_round >= max_round` -> END
  - else -> `question` (next round)
```

## Routing Rules

- `entry_llm -> ref` when both `user_answer` and `current_question` already exist in state.
- `entry_llm -> question` in normal startup flow.
- if `auto_answer_enabled=true`: `question -> auto_answer -> ref`
- if `auto_answer_enabled=false`: `question -> ref` (with user-submitted answer from API payload)
- `ref -> END` when rounds are finished; otherwise `ref -> question`.
