1. Goal Generation: Build a knowledge/skill tree. The learning process is to distill knowledge/skills from the LLM into the human brain.
2. Constructivist Educational Process: The distillation process follows constructionism. Human learners need a high-level understanding of the overall knowledge/skill tree and of each individual skill. This is a feed-forward process: the LLM evaluates the learner’s feed-forward knowledge construction, identifies errors and omissions (i.e., the loss), and then provides feedback (backpropagation). The learner performs feed-forward again, repeating this cycle until mastery is achieved.
3. Measurement and Review: During learning, the educational system measures and labels learning progress, and creates a review plan.
4. Reward Mechanism: Learning progress should be visualized, and students should receive immediate feedback signals.

## Theory-Project Relationship (Theory ↔ Agentic Learning Coach)

This project operationalizes the theory as an LLM-assisted human learning system. The four theoretical pillars map to concrete modules and state updates in the current implementation:

1. Goal Generation → Concept Initialization  
`entry_llm_node` transforms a user goal into `knowledge_graph_root` / `concepts` and initializes mastery-related fields (for example, `familiarity`). This is the engineering realization of defining the learnable knowledge/skill space before tutoring begins.

2. Constructivist Loop → Ask-Evaluate-Update Cycle  
`question_node` prompts learner expression (feed-forward), and `ref_node` evaluates responses, detects gaps (loss), and returns targeted feedback (backprop-style correction). The system then updates `qa_history` and `familiarity`, enabling iterative reconstruction of understanding round by round.

3. Measurement and Review → Persistent Progress Signals  
Per-round scores and historical Q&A traces provide measurable learning signals. The current system already supports continuous diagnosis; review scheduling is the natural next layer to turn measurement into explicit spaced reinforcement.

4. Reward Mechanism → Immediate Feedback and Future Gamification  
Immediate round-level feedback (`current_score`, `current_feedback`) already provides short-cycle reinforcement. Richer progress visualization and point-based motivation can extend this into a stronger long-cycle reward system.

In short, the project has implemented the core learning loop of the theory (goal modeling + diagnosis + feedback + progress tracking), and is evolving toward full theoretical coverage by adding review strategy and stronger incentive design.

## Improvement Suggestions (Based on the Theory)

To better align implementation with the four theoretical pillars, the project can be improved in the following directions:

1. Upgrade flat `concepts` into a hierarchical skill graph  
Add graph fields such as `prerequisites`, `children`, `difficulty`, and `importance`. This enables prerequisite-aware tutoring and branch expansion rather than treating concepts as an unordered list.

2. Replace simple low-familiarity sampling with a policy-based selector  
Use a composite score for question selection, for example: `uncertainty + forgetting_risk + importance + recency_penalty`. This makes intervention more targeted and consistent with constructivist error correction.

3. Improve mastery estimation beyond score averaging  
Evolve `familiarity` from a simple average to a lightweight mastery estimator (e.g., EMA/BKT-lite first, then Bayesian/IRT-style estimation). This yields a better concept-level loss signal and more stable progression control.

4. Add an explicit review scheduler  
Generate `next_review_at`, `interval`, and `stability` per concept. This turns passive measurement into actionable spaced review and operationalizes the "Measurement and Review" pillar.

5. Structure feedback for pedagogical action  
Split feedback into `what_is_wrong`, `why_wrong`, `minimal_fix`, and `next_action`, and provide layered reference answers (basic/standard/advanced). This improves correction quality and supports iterative feed-forward cycles.

6. Expand dialogue strategy types in `question_node`  
Support strategy modes such as explanation prompts, counterexamples, analogy, reverse questioning, and micro-quizzes. This shifts the system from single-mode assessment to adaptive teaching behavior.

7. Redefine completion criteria with mastery stability  
Do not rely only on `max_round`; finish when key concepts reach threshold mastery and pass stability/review checks. This prevents false completion when rounds end before real understanding is achieved.

8. Strengthen reward and visualization mechanisms  
Visualize concept heatmaps, forgetting risk, streaks, and milestones; connect rewards to high-quality learning behaviors (e.g., successful error correction, consistent review completion).

9. Add observability and test coverage for learning control  
Log decision rationale each round (why this concept/question, why this score/update). Add tests for graph migration, mastery updates, review scheduling, and termination criteria to prevent regressions as strategy logic evolves.