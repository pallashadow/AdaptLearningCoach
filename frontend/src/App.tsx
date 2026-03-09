import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { fetchDialogSnapshot, startDialog, submitAnswer } from "./api/dialogApi";
import type { AnswerResponse, StartDialogResponse } from "./types";
import { parseChoiceOptionsFromQuestion } from "./utils/choice";

const GITHUB_REPO_URL = "https://github.com/pallashadow/AdaptLearningCoach";

const githubDocPaths = [
  "README.md",
  "docs/PROPOSAL.md",
  "docs/THEORY.md",
  "docs/AGENT_GRAPH.md",
  "docs/README_GCLOUD_FUNCTIONS.md",
  "lib/agentic/prompts/entry_node_system.yaml",
  "lib/agentic/prompts/entry_node_user.yaml"
] as const;

const startSchema = z.object({
  backendUrl: z.string().url(),
  question: z.string().min(1, "Learning Goal is required."),
  question_mode: z.enum(["choice", "open"]),
  auto_answer_enabled: z.boolean(),
  max_round: z.number().int().min(1).max(20),
  auto_answer_proficiency: z.number().int().min(0).max(100)
});

const answerSchema = z.object({
  user_answer: z.string().optional()
});

type StartFormValues = z.infer<typeof startSchema>;
type AnswerFormValues = z.infer<typeof answerSchema>;
type HelpPopover = "maxRound" | "proficiency" | null;

function defaultChoiceOptions(): string[] {
  return ["Option A", "Option B", "Option C", "Option D"];
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildGithubDocLinks(): string {
  return githubDocPaths
    .map((path) => {
      const href = `${GITHUB_REPO_URL}/blob/main/${path}`;
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">${path}</a>`;
    })
    .join("");
}

export default function App() {
  const [dialogId, setDialogId] = useState("");
  const [finished, setFinished] = useState(false);
  const [currentQuestionMode, setCurrentQuestionMode] = useState<"open" | "choice">("choice");
  const [currentDialogAutoAnswer, setCurrentDialogAutoAnswer] = useState(false);
  const [activeDialogBaseUrl, setActiveDialogBaseUrl] = useState("");
  const [resultText, setResultText] = useState("No active dialog.");
  const [activeHelpPopover, setActiveHelpPopover] = useState<HelpPopover>(null);
  const [selectedChoice, setSelectedChoice] = useState("");
  const [currentQuestion, setCurrentQuestion] = useState("");
  const [currentRound, setCurrentRound] = useState(0);
  const [maxRound, setMaxRound] = useState(0);
  const [currentConcept, setCurrentConcept] = useState("");

  const startForm = useForm<StartFormValues>({
    resolver: zodResolver(startSchema),
    defaultValues: {
      backendUrl: "http://127.0.0.1:8001",
      question:
        "I am preparing for an ML Algorithm Engineer interview. Please start diagnostics.",
      question_mode: "choice",
      auto_answer_enabled: false,
      max_round: 5,
      auto_answer_proficiency: 60
    }
  });

  const answerForm = useForm<AnswerFormValues>({
    resolver: zodResolver(answerSchema),
    defaultValues: {
      user_answer: ""
    }
  });

  const normalizedBaseUrl = useMemo(
    () => startForm.watch("backendUrl").trim().replace(/\/+$/, ""),
    [startForm]
  );

  const dialogQuery = useQuery({
    queryKey: ["dialog-snapshot", dialogId, activeDialogBaseUrl],
    queryFn: () => fetchDialogSnapshot(activeDialogBaseUrl, dialogId),
    enabled: Boolean(dialogId && activeDialogBaseUrl)
  });

  useEffect(() => {
    function handleClickOutside() {
      if (activeHelpPopover) {
        setActiveHelpPopover(null);
      }
    }

    function handleEsc(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setActiveHelpPopover(null);
      }
    }

    document.addEventListener("click", handleClickOutside);
    document.addEventListener("keydown", handleEsc);
    return () => {
      document.removeEventListener("click", handleClickOutside);
      document.removeEventListener("keydown", handleEsc);
    };
  }, [activeHelpPopover]);

  const startMutation = useMutation({
    mutationFn: async (values: StartFormValues) => {
      return startDialog(values.backendUrl, {
        question: values.question.trim(),
        max_round: values.max_round,
        auto_answer_enabled: values.auto_answer_enabled,
        auto_answer_proficiency: values.auto_answer_proficiency,
        question_mode: values.question_mode
      });
    },
    onSuccess: async (data: StartDialogResponse, values: StartFormValues) => {
      setDialogId(data.dialog_id);
      setFinished(false);
      setCurrentQuestionMode(values.question_mode);
      setCurrentDialogAutoAnswer(values.auto_answer_enabled);
      setActiveDialogBaseUrl(values.backendUrl.trim().replace(/\/+$/, ""));
      setCurrentQuestion(data.current_question);
      setCurrentRound(data.current_round);
      setMaxRound(data.max_round);
      setCurrentConcept(data.current_concept);
      setSelectedChoice("");
      answerForm.setValue("user_answer", "");
      setResultText(
        `Current question:\n${data.current_question}\n\nKnowledge root:\n${JSON.stringify(
          data.knowledge_graph_root,
          null,
          2
        )}`
      );

    },
    onError: (error) => {
      setActiveDialogBaseUrl("");
      setResultText(`Start failed:\n${String(error)}`);
    }
  });

  const answerMutation = useMutation({
    mutationFn: async (values: AnswerFormValues) => {
      const userAnswer =
        currentQuestionMode === "choice" ? selectedChoice : values.user_answer?.trim() ?? "";

      if (!currentDialogAutoAnswer && !userAnswer) {
        throw new Error(
          currentQuestionMode === "choice"
            ? "Single-choice mode: please select exactly one option."
            : "Please input your answer first."
        );
      }

      return submitAnswer(activeDialogBaseUrl || normalizedBaseUrl, {
        dialog_id: dialogId,
        user_answer: userAnswer
      });
    },
    onSuccess: async (data: AnswerResponse) => {
      setFinished(data.finished);
      setCurrentRound(data.current_round);
      setMaxRound(data.max_round);
      setCurrentConcept(data.current_concept);
      setCurrentQuestion(data.current_question);
      setSelectedChoice("");
      answerForm.setValue("user_answer", "");

      setResultText(
        `Feedback:\n${data.current_feedback}\n\nScore: ${data.current_score}\n\nGround Truth:\n${
          data.last_ground_truth
        }\n\n${data.finished ? "Dialog finished." : `Next question:\n${data.current_question}`}`
      );

    },
    onError: (error) => {
      const rawError = String(error);
      const notFoundDialog = rawError.includes("dialog_id not found");
      setResultText(
        notFoundDialog
          ? `Submit failed:\n${rawError}\n\nThis dialog does not exist in the active backend anymore. Start a new dialog (the backend may have restarted or changed).`
          : `Submit failed:\n${rawError}`
      );
    }
  });

  const choiceOptions = useMemo(() => {
    const parsed = parseChoiceOptionsFromQuestion(currentQuestion);
    return parsed.length === 4 ? parsed : defaultChoiceOptions();
  }, [currentQuestion]);

  const dialogMeta = dialogId
    ? `dialog_id=${dialogId} | round=${currentRound}/${maxRound} | concept=${currentConcept || "-"}`
    : "No active dialog.";

  const isChoiceMode = dialogId ? currentQuestionMode === "choice" : startForm.watch("question_mode") === "choice";

  return (
    <div className="layout">
      <section className="main-panel">
        <h1>Agentic Learning</h1>

        <form
          onSubmit={startForm.handleSubmit((values) => startMutation.mutate(values))}
          className="row-stack"
        >
          <div className="row">
            <label htmlFor="backendUrl">Backend URL</label>
            <input id="backendUrl" {...startForm.register("backendUrl")} />
          </div>

          <div className="row">
            <label htmlFor="question">Learning Goal / Interview Goal</label>
            <textarea id="question" {...startForm.register("question")} />
          </div>

          <div className="row">
            <div className="inline-controls">
              <label className="compact-field" htmlFor="questionMode">
                <span>Question Mode</span>
                <select id="questionMode" {...startForm.register("question_mode")}>
                  <option value="choice">Single Choice</option>
                  <option value="open">Open-ended</option>
                </select>
              </label>

              <label className="checkbox-row" htmlFor="autoAnswer">
                <input id="autoAnswer" type="checkbox" {...startForm.register("auto_answer_enabled")} />
                <span>Auto Answer</span>
              </label>

              <label className="compact-field" htmlFor="maxRound">
                <span className="field-label-with-help">
                  Main Questions
                  <button
                    type="button"
                    className="info-icon"
                    aria-label="Explain main questions"
                    aria-controls="maxRoundHelp"
                    aria-expanded={activeHelpPopover === "maxRound"}
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      setActiveHelpPopover((current) =>
                        current === "maxRound" ? null : "maxRound"
                      );
                    }}
                  >
                    i
                  </button>
                  {activeHelpPopover === "maxRound" ? (
                    <span id="maxRoundHelp" className="help-popover">
                      Number of main diagnostic questions in one dialog. Recommended 3-8.
                    </span>
                  ) : null}
                </span>
                <input
                  id="maxRound"
                  type="number"
                  min={1}
                  max={20}
                  {...startForm.register("max_round", { valueAsNumber: true })}
                />
              </label>

              <label className="compact-field" htmlFor="autoAnswerProficiency">
                <span className="field-label-with-help">
                  Proficiency (%)
                  <button
                    type="button"
                    className="info-icon"
                    aria-label="Explain proficiency"
                    aria-controls="proficiencyHelp"
                    aria-expanded={activeHelpPopover === "proficiency"}
                    onClick={(event) => {
                      event.preventDefault();
                      event.stopPropagation();
                      setActiveHelpPopover((current) =>
                        current === "proficiency" ? null : "proficiency"
                      );
                    }}
                  >
                    i
                  </button>
                  {activeHelpPopover === "proficiency" ? (
                    <span id="proficiencyHelp" className="help-popover">
                      Target proficiency used by Auto Answer. Higher means stronger simulated answers.
                    </span>
                  ) : null}
                </span>
                <input
                  id="autoAnswerProficiency"
                  type="number"
                  min={0}
                  max={100}
                  disabled={!startForm.watch("auto_answer_enabled")}
                  {...startForm.register("auto_answer_proficiency", { valueAsNumber: true })}
                />
              </label>
            </div>
          </div>

          <div className="row">
            <button type="submit" disabled={startMutation.isPending}>
              Start Dialog
            </button>
          </div>
        </form>

        <p className="muted">{dialogMeta}</p>

        <form
          onSubmit={answerForm.handleSubmit((values) => answerMutation.mutate(values))}
          className="row-stack"
        >
          {!isChoiceMode ? (
            <div className="row">
              <label htmlFor="answer">Your Answer</label>
              <textarea
                id="answer"
                placeholder={
                  currentDialogAutoAnswer
                    ? "Auto Answer is enabled. The system will generate responses based on the selected proficiency."
                    : "Type your answer for current question..."
                }
                disabled={currentDialogAutoAnswer}
                {...answerForm.register("user_answer")}
              />
            </div>
          ) : (
            <div className="row">
              <label>Select exactly one option</label>
              <div className="choice-options">
                {choiceOptions.map((text, idx) => {
                  const label = ["A", "B", "C", "D"][idx] ?? "";
                  return (
                    <label key={label} className="radio-option">
                      <input
                        type="radio"
                        name="choiceAnswer"
                        value={label}
                        checked={selectedChoice === label}
                        disabled={currentDialogAutoAnswer}
                        onChange={(event) => setSelectedChoice(event.target.value)}
                      />
                      <span dangerouslySetInnerHTML={{ __html: `<strong>${label}.</strong> ${escapeHtml(text)}` }} />
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          <div className="row">
            <button
              type="submit"
              disabled={!dialogId || finished || answerMutation.isPending || startMutation.isPending}
            >
              Submit Answer
            </button>
          </div>
        </form>

        <div className="result">{resultText}</div>

        <div className="row docs-row">
          <label>GitHub Docs</label>
          <div className="doc-links" dangerouslySetInnerHTML={{ __html: buildGithubDocLinks() }} />
        </div>
      </section>

      <aside className="state-panel">
        <h2>Current State</h2>
        <pre className="state-view">
          {dialogQuery.isLoading
            ? "Loading state..."
            : dialogQuery.error
              ? `State update failed:\n${String(dialogQuery.error)}`
              : dialogQuery.data?.state
                ? JSON.stringify(dialogQuery.data.state, null, 2)
                : "No active dialog."}
        </pre>
      </aside>
    </div>
  );
}

