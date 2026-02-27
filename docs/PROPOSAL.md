# Agentic Learning Todo List

- [x] Root node generation: create the soft knowledge graph root node `knowledge_graph_root` based on the user's goal
- [x] Upgrade root node structure to a `concepts` list, where each concept includes:
  - `concept`
  - `familiarity` (initially 0)
  - `posterior_question_count` (initially 0)
  - `qa_history` (initially an empty list, with items as `{question, answer, score}`)
- [x] Update familiarity based on historical question scores (currently the average of `qa_history.score`)
- [x] Support legacy schema fields (`topic_nodes/mastered_concepts/vague_concepts/misconceptions`) and migrate them to `concepts`

- [ ] Implement posterior update for a single concept (after each Q&A round, auto-append to `qa_history` and recompute familiarity)
- [ ] Design diagnostic questioning strategy: prioritize sampling by `familiarity`, test low-familiarity concepts more and high-familiarity concepts less
- [ ] Support branch logic: skip when familiar, expand leaf nodes when unfamiliar
- [ ] Add a leaf-node expansion mechanism for each concept (e.g., BCE -> Bernoulli distribution -> likelihood function)
- [ ] Add learning dialogue strategies (explanation, follow-up, reverse questioning, analogy) and continuously enrich the graph
- [ ] Complete termination condition and progress visualization for "all root concepts reach 100% mastery"

- [ ] Design a points system (answer quality, question depth, continuous learning duration)
- [ ] Map points to a text-based battle system (monster HP, approach timer, XP, and equipment)
- [ ] Add tests for key workflows:
  - Structure initialization test
  - Posterior update and familiarity computation test
  - Legacy schema migration compatibility test
