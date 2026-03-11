import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { fetchDialogSnapshot, resetUserState, startDialog, submitAnswer } from "./api/dialogApi";
import type { AnswerResponse, StartDialogResponse } from "./types";
import { extractChoiceStemFromQuestion, parseChoiceOptionsFromQuestion } from "./utils/choice";

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

type UIQuestionMode = "choice_2" | "choice_3" | "choice_4" | "open";

type BackendQuestionMode = "open" | "choice";

function parseUiQuestionMode(mode: UIQuestionMode): {
  questionMode: BackendQuestionMode;
  choiceOptionCount: 2 | 3 | 4;
} {
  if (mode === "open") {
    return { questionMode: "open", choiceOptionCount: 4 };
  }
  if (mode === "choice_2") {
    return { questionMode: "choice", choiceOptionCount: 2 };
  }
  if (mode === "choice_3") {
    return { questionMode: "choice", choiceOptionCount: 3 };
  }
  return { questionMode: "choice", choiceOptionCount: 4 };
}

const startSchema = z.object({
  backendUrl: z.string().url(),
  user_id: z.string().min(1, "User ID is required."),
  question: z.string().min(1, "Learning Goal is required."),
  question_mode: z.enum(["choice_2", "choice_3", "choice_4", "open"]),
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

function optionLabels(optionCount: number): string[] {
  return ["A", "B", "C", "D"].slice(0, Math.max(2, Math.min(4, optionCount)));
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
  const [isStartConfigCollapsed, setIsStartConfigCollapsed] = useState(false);
  const [currentQuestionMode, setCurrentQuestionMode] = useState<BackendQuestionMode>("choice");
  const [currentChoiceOptionCount, setCurrentChoiceOptionCount] = useState<2 | 3 | 4>(4);
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
      user_id: "demo-user",
      question:
        "I am preparing for an ML Algorithm Engineer interview. Please start diagnostics.",
      question_mode: "choice_4",
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
      const parsedMode = parseUiQuestionMode(values.question_mode as UIQuestionMode);
      return startDialog(values.backendUrl, {
        question: values.question.trim(),
        user_id: values.user_id.trim(),
        max_round: values.max_round,
        auto_answer_enabled: values.auto_answer_enabled,
        auto_answer_proficiency: values.auto_answer_proficiency,
        question_mode: parsedMode.questionMode,
        choice_option_count: parsedMode.choiceOptionCount
      });
    },
    onSuccess: (data: StartDialogResponse, values: StartFormValues) => {
      const parsedMode = parseUiQuestionMode(values.question_mode as UIQuestionMode);
      setDialogId(data.dialog_id);
      setFinished(false);
      setIsStartConfigCollapsed(true);
      setCurrentQuestionMode(parsedMode.questionMode);
      setCurrentChoiceOptionCount(parsedMode.choiceOptionCount);
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

  const resetMutation = useMutation({
    mutationFn: async (values: { backendUrl: string; userId: string }) =>
      resetUserState(values.backendUrl, values.userId),
    onSuccess: (data) => {
      setDialogId("");
      setFinished(false);
      setActiveDialogBaseUrl("");
      setCurrentQuestion("");
      setCurrentRound(0);
      setMaxRound(0);
      setCurrentConcept("");
      setSelectedChoice("");
      answerForm.setValue("user_answer", "");
      setResultText(
        `User state reset complete for '${data.user_id}'.\nDeleted dialogs: ${data.deleted_dialogs}\nDeleted concepts: ${data.deleted_concepts}\nDeleted profile: ${data.deleted_profile}\nDeleted legacy state: ${data.deleted_legacy_state}`
      );
    },
    onError: (error) => {
      setResultText(`Reset user state failed:\n${String(error)}`);
    }
  });

  const answerMutation = useMutation({
    mutationFn: async (values: AnswerFormValues) => {
      const userAnswer =
        currentQuestionMode === "choice" ? selectedChoice : values.user_answer?.trim() ?? "";
      const parsedChoiceOptions = parseChoiceOptionsFromQuestion(currentQuestion);
      const hasValidChoiceQuestion =
        parsedChoiceOptions.length >= 2 && parsedChoiceOptions.length <= 4;

      if (!currentDialogAutoAnswer && !userAnswer) {
        throw new Error(
          currentQuestionMode === "choice"
            ? "Single-choice mode: please select exactly one option."
            : "Please input your answer first."
        );
      }
      if (currentQuestionMode === "choice" && !hasValidChoiceQuestion) {
        throw new Error(
          "Current question is invalid (failed to parse options). This question cannot be answered. Please restart dialog."
        );
      }

      return submitAnswer(activeDialogBaseUrl || normalizedBaseUrl, {
        dialog_id: dialogId,
        user_answer: userAnswer
      });
    },
    onSuccess: (data: AnswerResponse) => {
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

  const parsedChoiceOptions = useMemo(
    () => parseChoiceOptionsFromQuestion(currentQuestion),
    [currentQuestion]
  );
  const choiceQuestionStem = useMemo(
    () => extractChoiceStemFromQuestion(currentQuestion),
    [currentQuestion]
  );
  const hasValidChoiceQuestion =
    parsedChoiceOptions.length >= 2 &&
    parsedChoiceOptions.length <= 4 &&
    parsedChoiceOptions.length === currentChoiceOptionCount;
  const choiceOptions = hasValidChoiceQuestion ? parsedChoiceOptions : [];

  const choiceLabels = useMemo(() => optionLabels(choiceOptions.length), [choiceOptions.length]);

  const dialogMeta = dialogId
    ? `dialog_id=${dialogId} | round=${currentRound}/${maxRound} | concept=${currentConcept || "-"}`
    : "No active dialog.";

  const watchedUiMode = startForm.watch("question_mode") as UIQuestionMode;
  const isChoiceMode = dialogId
    ? currentQuestionMode === "choice"
    : parseUiQuestionMode(watchedUiMode).questionMode === "choice";

  return (
    <div className="layout">
      <section className="main-panel">
        <h1>Agentic Learning</h1>

        <div className="section-toggle-row">
          <button
            type="button"
            className="secondary-button"
            onClick={() => setIsStartConfigCollapsed((current) => !current)}
            aria-expanded={!isStartConfigCollapsed}
          >
            {isStartConfigCollapsed ? "Expand Start Config" : "Collapse Start Config"}
          </button>
        </div>

        {!isStartConfigCollapsed ? (
          <form
            onSubmit={startForm.handleSubmit((values) => startMutation.mutate(values))}
            className="row-stack"
          >
          <div className="row">
            <label htmlFor="backendUrl">Backend URL</label>
            <input id="backendUrl" {...startForm.register("backendUrl")} />
          </div>

          <div className="row">
            <label htmlFor="userId">User ID</label>
            <input id="userId" {...startForm.register("user_id")} />
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
                    <option value="choice_2">Single Choice (2 options)</option>
                    <option value="choice_3">Single Choice (3 options)</option>
                    <option value="choice_4">Single Choice (4 options)</option>
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
            <button
              type="button"
              disabled={startMutation.isPending || resetMutation.isPending}
              onClick={() => {
                const values = startForm.getValues();
                const userId = values.user_id.trim();
                const backendUrl = values.backendUrl.trim();
                if (!userId) {
                  setResultText("Reset user state failed:\nuser_id is required.");
                  return;
                }
                if (!backendUrl) {
                  setResultText("Reset user state failed:\nbackendUrl is required.");
                  return;
                }
                resetMutation.mutate({ backendUrl, userId });
              }}
            >
              Reset User State
            </button>
          </div>
        </form>
        ) : null}

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
              <div className="question-stem">{choiceQuestionStem}</div>
              <label>Select exactly one option</label>
              {!hasValidChoiceQuestion ? (
                <div className="result">
                  Failed to render question options. Backend returned an invalid choice question.
                  Please restart dialog.
                </div>
              ) : (
                <div className="choice-options">
                  {choiceOptions.map((text, idx) => {
                    const label = choiceLabels[idx] ?? "";
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
              )}
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

