# Harness Engineering (Notes)

Source: https://openai.com/index/harness-engineering/  
Title: Harness engineering: leveraging Codex in an agent-first world  
Date: 2026-02-11  
Author: Ryan Lopopolo

## 1) Core Conclusions

- In agent-first software development, the main human job shifts from writing code directly to designing environments, constraints, and feedback loops.
- The speedup comes not only from stronger models, but from an executable engineering system: documentation structure, architectural boundaries, automated checks, observability, and continuous cleanup.
- The repository should be the system of record. Knowledge that is not visible to agents is effectively non-existent.

## 2) Practical Takeaways from the Article

## Starting from an Empty Repository, with Agents Producing the Full Stack
- The team started from a blank repository and used Codex to generate application code, tests, CI configuration, documentation, and internal tools.
- Development moved forward through high-frequency PR loops, with humans owning goals and acceptance criteria instead of manually writing product code.

## Redefining the Engineer's Role
- The focus becomes "task decomposition + capability gap closure":
  - Break large goals into executable sub-tasks.
  - When an agent gets stuck, add tools, constraints, and documentation instead of bypassing with manual coding.

## Improving Application Legibility, Not Just Code Legibility
- Enable agents to directly read and drive the UI (for example via browser protocols, DOM snapshots, and screenshots).
- Make logs, metrics, and traces queryable context for agents, so they can reproduce issues, validate fixes, and run regressions.

## Keep `AGENTS.md` Short; Keep `docs/` Structured
- Avoid the "one giant instruction file" approach.
- Recommended pattern:
  - Keep `AGENTS.md` concise as a navigation index.
  - Use structured `docs/` as a knowledge base.
  - Use lint/CI to validate doc freshness, links, and structure.
  - Run periodic "docs gardening" tasks to repair outdated documentation.

## The Goal Is Agent Legibility
- Prioritize writing key knowledge into the repository (code, Markdown, schemas, plans, and rules).
- Prefer stable, composable, predictable abstractions and dependencies to reduce black-box behavior.

## Governing Architecture Through Invariants
- Enforce architecture with layered boundaries and dependency direction constraints.
- Use custom lint rules and structural tests to mechanically enforce rules, encoding team taste into the system.

## Throughput Changes Process Philosophy
- In high-throughput agent-driven development, waiting can cost more than fixing.
- PR lifecycles get shorter, and many issues are resolved through rapid iteration and follow-up fixes.

## Autonomy Increases, but Depends on Engineering Investment
- Agents can execute end-to-end flows: reproduce, fix, validate, open PRs, respond to feedback, repair builds, and merge.
- This depends on repository structure, tooling, and standards; it is not zero-cost generalization.

## Entropy Management (Garbage Collection) Is a Long-Term Requirement
- Agents replicate existing patterns, including bad ones, so drift is inevitable.
- Continuous garbage collection is required:
  - Encode golden rules.
  - Run background drift detection.
  - Open targeted small refactoring PRs to continuously pay down technical debt.

## 3) Actionable Framework (Short Version)

1. Keep `AGENTS.md` at the level of a navigation index (short, stable, executable).  
2. Layer `docs/`: architecture, product specs, execution plans, references, and generated docs.  
3. Provide observability entry points for agents: logs, metrics, traces, and UI validation capabilities.  
4. Turn architecture boundaries, naming, size limits, and reliability requirements into hard rules via lint/CI.  
5. Maintain an active cleanup loop: scan drift regularly and open automated repair PRs.  
6. Keep humans focused on high-leverage work: goal setting, acceptance criteria, risk judgment, and system design.  

## 4) Implications for This Repository (`agentic_learning`)

- Keep the current pattern: a concise `AGENTS.md` plus structured `docs/`.
- Strengthen support for high-frequency SQL/PySpark tasks:
  - A runbook for both execution paths (Databricks SQL vs. PySpark).
  - Field-mapping and metric-definition dictionaries (`_id/uid/init_id/user_id`).
  - Common request templates and validation checklists.
- Reduce drift with automation checks:
  - Documentation link validation.
  - Static checks for key rules (restricted directories, default profile, minimum validation steps).

## 5) One-Sentence Summary

In the agent era, engineering productivity depends less on "getting the model to write more code" and more on building an engineering system that agents can reliably understand, execute, and continuously self-correct.
