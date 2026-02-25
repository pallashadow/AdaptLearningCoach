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

const app = document.querySelector<HTMLDivElement>("#app");
if (!app) {
  throw new Error("App root not found");
}

app.innerHTML = `
  <h1>Agentic Learning</h1>
  <div class="row">
    <label for="backendUrl">Backend URL</label>
    <input id="backendUrl" value="http://127.0.0.1:8000" />
  </div>
  <div class="row">
    <label for="question">Learning Goal / Interview Goal</label>
    <textarea id="question">I am preparing for an ML Algorithm Engineer interview. Please start diagnostics.</textarea>
  </div>
  <div class="row">
    <label for="maxRound">Max Round</label>
    <input id="maxRound" type="number" min="1" max="20" value="5" />
  </div>
  <div class="row">
    <button id="startBtn">Start Dialog</button>
  </div>
  <p id="dialogMeta" class="muted">No active dialog.</p>
  <div class="row">
    <label for="answer">Your Answer</label>
    <textarea id="answer" placeholder="Type your answer for current question..."></textarea>
  </div>
  <div class="row">
    <button id="sendBtn" disabled>Submit Answer</button>
  </div>
  <div id="result" class="result"></div>
`;

const backendUrlInput = document.querySelector<HTMLInputElement>("#backendUrl")!;
const questionInput = document.querySelector<HTMLTextAreaElement>("#question")!;
const maxRoundInput = document.querySelector<HTMLInputElement>("#maxRound")!;
const answerInput = document.querySelector<HTMLTextAreaElement>("#answer")!;
const startBtn = document.querySelector<HTMLButtonElement>("#startBtn")!;
const sendBtn = document.querySelector<HTMLButtonElement>("#sendBtn")!;
const dialogMeta = document.querySelector<HTMLParagraphElement>("#dialogMeta")!;
const result = document.querySelector<HTMLDivElement>("#result")!;

let dialogId = "";
let finished = false;

function renderResult(text: string) {
  result.textContent = text;
}

function getBaseUrl(): string {
  return backendUrlInput.value.trim().replace(/\/+$/, "");
}

function updateMeta(round: number, maxRound: number, concept: string) {
  dialogMeta.textContent = `dialog_id=${dialogId} | round=${round}/${maxRound} | concept=${concept || "-"}`;
}

startBtn.addEventListener("click", async () => {
  try {
    startBtn.disabled = true;
    sendBtn.disabled = true;
    finished = false;

    const payload = {
      question: questionInput.value.trim(),
      max_round: Number(maxRoundInput.value)
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
    sendBtn.disabled = false;
    updateMeta(data.current_round, data.max_round, data.current_concept);
    renderResult(
      `Current question:\n${data.current_question}\n\nKnowledge root:\n${JSON.stringify(
        data.knowledge_graph_root,
        null,
        2
      )}`
    );
  } catch (error) {
    renderResult(`Start failed:\n${String(error)}`);
  } finally {
    startBtn.disabled = false;
  }
});

sendBtn.addEventListener("click", async () => {
  if (!dialogId || finished) {
    return;
  }
  const userAnswer = answerInput.value.trim();
  if (!userAnswer) {
    renderResult("Please input your answer first.");
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
    updateMeta(data.current_round, data.max_round, data.current_concept);
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
  } finally {
    sendBtn.disabled = finished;
  }
});
