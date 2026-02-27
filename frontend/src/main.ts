import "./style.css";

type StartDialogResponse = {
  dialog_id: string;
  current_round: number;
  max_round: number;
  current_question: string;
  current_concept: string;
  knowledge_graph_root: Record<string, unknown>;
};

type AnswerResponse = {
  dialog_id: string;
  finished: boolean;
  current_round: number;
  max_round: number;
  current_concept: string;
  current_question: string;
  current_feedback: string;
  current_score: number;
  last_ground_truth: string;
};

type DialogSnapshotResponse = {
  dialog_id: string;
  created_at: string;
  updated_at: string;
  finished: boolean;
  state: Record<string, unknown>;
};

const GITHUB_REPO_URL = "https://github.com/pallashadow/AdaptLearningCoach";

const githubDocPaths = [
  "README.md",
  "docs/PROPOSAL.md",
  "docs/THEORY.md",
  "docs/AGENT_GRAPH.md",
  "docs/README_GCLOUD_FUNCTIONS.md",
  "lib/agentic/prompts/entry_node_system.yaml",
  "lib/agentic/prompts/entry_node_user.yaml"
];

function buildGithubDocLinks(): string {
  return githubDocPaths
    .map((path) => {
      const href = `${GITHUB_REPO_URL}/blob/main/${path}`;
      return `<a href="${href}" target="_blank" rel="noopener noreferrer">${path}</a>`;
    })
    .join("");
}

const app = document.querySelector<HTMLDivElement>("#app");
if (!app) {
  throw new Error("App root not found");
}

app.innerHTML = `
  <div class="layout">
    <section class="main-panel">
      <h1>Agentic Learning</h1>
      <div class="row">
        <label for="backendUrl">Backend URL</label>
        <input id="backendUrl" value="http://127.0.0.1:8001" />
      </div>
      <div class="row">
        <label for="question">Learning Goal / Interview Goal</label>
        <textarea id="question">I am preparing for an ML Algorithm Engineer interview. Please start diagnostics.</textarea>
      </div>
      <div class="row">
        <div class="inline-controls">
          <label class="compact-field" for="questionMode">
            <span>Question Mode</span>
            <select id="questionMode">
              <option value="choice" selected>Multiple Choice</option>
              <option value="open">Open-ended</option>
            </select>
          </label>
          <label class="checkbox-row" for="autoAnswer">
            <input id="autoAnswer" type="checkbox" />
            <span>Auto Answer</span>
          </label>
          <label class="compact-field" for="maxRound">
            <span>Max Round</span>
            <input id="maxRound" type="number" min="1" max="20" value="5" disabled />
          </label>
          <label class="compact-field" for="autoAnswerProficiency">
            <span>Proficiency (%)</span>
            <input id="autoAnswerProficiency" type="number" min="0" max="100" value="60" disabled />
          </label>
        </div>
      </div>
      <div class="row">
        <button id="startBtn">Start Dialog</button>
      </div>
      <p id="dialogMeta" class="muted">No active dialog.</p>
      <div class="row">
        <label for="answer">Your Answer</label>
        <textarea id="answer" placeholder="Type your answer for current question..."></textarea>
      </div>
      <div class="row hidden" id="choiceAnswerRow">
        <label>Select an Option</label>
        <div id="choiceOptions" class="choice-options"></div>
      </div>
      <div class="row">
        <button id="sendBtn" disabled>Submit Answer</button>
      </div>
      <div id="result" class="result"></div>
      <div class="row docs-row">
        <label>GitHub Docs</label>
        <div class="doc-links">
          ${buildGithubDocLinks()}
        </div>
      </div>
    </section>
    <aside class="state-panel">
      <h2>Current State</h2>
      <pre id="stateView" class="state-view">No active dialog.</pre>
    </aside>
  </div>
`;

const backendUrlInput = document.querySelector<HTMLInputElement>("#backendUrl")!;
const questionInput = document.querySelector<HTMLTextAreaElement>("#question")!;
const questionModeInput = document.querySelector<HTMLSelectElement>("#questionMode")!;
const autoAnswerInput = document.querySelector<HTMLInputElement>("#autoAnswer")!;
const maxRoundInput = document.querySelector<HTMLInputElement>("#maxRound")!;
const autoAnswerProficiencyInput = document.querySelector<HTMLInputElement>("#autoAnswerProficiency")!;
const answerInput = document.querySelector<HTMLTextAreaElement>("#answer")!;
const choiceAnswerRow = document.querySelector<HTMLDivElement>("#choiceAnswerRow")!;
const choiceOptions = document.querySelector<HTMLDivElement>("#choiceOptions")!;
const startBtn = document.querySelector<HTMLButtonElement>("#startBtn")!;
const sendBtn = document.querySelector<HTMLButtonElement>("#sendBtn")!;
const dialogMeta = document.querySelector<HTMLParagraphElement>("#dialogMeta")!;
const result = document.querySelector<HTMLDivElement>("#result")!;
const stateView = document.querySelector<HTMLPreElement>("#stateView")!;

let dialogId = "";
let finished = false;
let currentDialogAutoAnswer = false;
let currentDialogQuestionMode: "open" | "choice" = "choice";

function getSelectedQuestionMode(): "open" | "choice" {
  return questionModeInput.value === "open" ? "open" : "choice";
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function parseChoiceOptionsFromQuestion(question: string): string[] {
  const lines = question.split(/\r?\n/);
  const options: string[] = [];
  for (const line of lines) {
    const match = line.match(/^\s*[A-D][\.\)]\s+(.+)$/i);
    if (!match) {
      continue;
    }
    options.push(match[1].trim());
  }
  return options.length === 4 ? options : [];
}

function renderChoiceOptions(question: string) {
  const parsedOptions = parseChoiceOptionsFromQuestion(question);
  const options = parsedOptions.length === 4
    ? parsedOptions
    : [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
      ];
  const labels = ["A", "B", "C", "D"];
  choiceOptions.innerHTML = options
    .map(
      (text, idx) => `
        <label class="radio-option">
          <input type="radio" name="choiceAnswer" value="${labels[idx]}" />
          <span><strong>${labels[idx]}.</strong> ${escapeHtml(text)}</span>
        </label>
      `
    )
    .join("");
}

function getChoiceAnswer(): string {
  const selected = document.querySelector<HTMLInputElement>('input[name="choiceAnswer"]:checked');
  return selected?.value ?? "";
}

function syncAnswerInputMode() {
  const mode = dialogId ? currentDialogQuestionMode : getSelectedQuestionMode();
  const autoEnabled = dialogId ? currentDialogAutoAnswer : autoAnswerInput.checked;
  const isChoiceMode = mode === "choice";

  if (isChoiceMode) {
    answerInput.parentElement?.classList.add("hidden");
    choiceAnswerRow.classList.remove("hidden");
  } else {
    answerInput.parentElement?.classList.remove("hidden");
    choiceAnswerRow.classList.add("hidden");
  }

  answerInput.disabled = autoEnabled || isChoiceMode;
  answerInput.placeholder = autoEnabled
    ? "Auto Answer is enabled. The system will generate responses based on the selected proficiency."
    : "Type your answer for current question...";

  const radioInputs = choiceOptions.querySelectorAll<HTMLInputElement>('input[name="choiceAnswer"]');
  radioInputs.forEach((input) => {
    input.disabled = autoEnabled || !isChoiceMode;
  });
}

function renderResult(text: string) {
  result.textContent = text;
}

function renderState(state: Record<string, unknown> | string) {
  if (typeof state === "string") {
    stateView.textContent = state;
    return;
  }
  stateView.textContent = JSON.stringify(state, null, 2);
}

function getBaseUrl(): string {
  return backendUrlInput.value.trim().replace(/\/+$/, "");
}

function updateMeta(round: number, maxRound: number, concept: string) {
  dialogMeta.textContent = `dialog_id=${dialogId} | round=${round}/${maxRound} | concept=${concept || "-"}`;
}

function syncMaxRoundInput() {
  const enabled = autoAnswerInput.checked;
  maxRoundInput.disabled = !enabled;
  autoAnswerProficiencyInput.disabled = !enabled;
  syncAnswerInputMode();
}

async function refreshState(): Promise<void> {
  if (!dialogId) {
    renderState("No active dialog.");
    return;
  }
  const resp = await fetch(`${getBaseUrl()}/dialogs/${dialogId}`);
  if (!resp.ok) {
    throw new Error(await resp.text());
  }
  const snapshot = (await resp.json()) as DialogSnapshotResponse;
  renderState(snapshot.state ?? {});
}

autoAnswerInput.addEventListener("change", () => {
  syncMaxRoundInput();
});
questionModeInput.addEventListener("change", () => {
  syncAnswerInputMode();
});
syncMaxRoundInput();

startBtn.addEventListener("click", async () => {
  try {
    startBtn.disabled = true;
    sendBtn.disabled = true;
    finished = false;
    currentDialogAutoAnswer = autoAnswerInput.checked;
    currentDialogQuestionMode = getSelectedQuestionMode();
    syncMaxRoundInput();

    const payload = {
      question: questionInput.value.trim(),
      max_round: Number(maxRoundInput.value),
      auto_answer_enabled: autoAnswerInput.checked,
      auto_answer_proficiency: Number(autoAnswerProficiencyInput.value),
      question_mode: currentDialogQuestionMode
    };

    const resp = await fetch(`${getBaseUrl()}/dialogs/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!resp.ok) {
      throw new Error(await resp.text());
    }

    const data = (await resp.json()) as StartDialogResponse;
    dialogId = data.dialog_id;
    if (currentDialogQuestionMode === "choice") {
      renderChoiceOptions(data.current_question);
    }
    syncAnswerInputMode();
    sendBtn.disabled = false;
    updateMeta(data.current_round, data.max_round, data.current_concept);
    await refreshState();
    renderResult(
      `Current question:\n${data.current_question}\n\nKnowledge root:\n${JSON.stringify(
        data.knowledge_graph_root,
        null,
        2
      )}`
    );
  } catch (error) {
    renderResult(`Start failed:\n${String(error)}`);
    renderState(`State update failed:\n${String(error)}`);
  } finally {
    startBtn.disabled = false;
  }
});

sendBtn.addEventListener("click", async () => {
  if (!dialogId || finished) {
    return;
  }
  const userAnswer = currentDialogQuestionMode === "choice"
    ? getChoiceAnswer()
    : answerInput.value.trim();
  if (!currentDialogAutoAnswer && !userAnswer) {
    renderResult(
      currentDialogQuestionMode === "choice"
        ? "Please select an option first."
        : "Please input your answer first."
    );
    return;
  }

  try {
    sendBtn.disabled = true;
    const resp = await fetch(`${getBaseUrl()}/dialogs/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dialog_id: dialogId,
        user_answer: userAnswer
      })
    });
    if (!resp.ok) {
      throw new Error(await resp.text());
    }

    const data = (await resp.json()) as AnswerResponse;
    finished = data.finished;
    if (!data.finished && currentDialogQuestionMode === "choice") {
      renderChoiceOptions(data.current_question);
    }
    syncAnswerInputMode();
    updateMeta(data.current_round, data.max_round, data.current_concept);
    await refreshState();
    renderResult(
      `Feedback:\n${data.current_feedback}\n\nScore: ${data.current_score}\n\nGround Truth:\n${
        data.last_ground_truth
      }\n\n${
        data.finished
          ? "Dialog finished."
          : `Next question:\n${data.current_question}`
      }`
    );
    answerInput.value = "";
  } catch (error) {
    renderResult(`Submit failed:\n${String(error)}`);
    renderState(`State update failed:\n${String(error)}`);
  } finally {
    sendBtn.disabled = finished;
  }
});
