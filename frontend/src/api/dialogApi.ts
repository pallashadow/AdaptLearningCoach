import type {
  AnswerResponse,
  DialogSnapshotResponse,
  ResetUserStateResponse,
  StartDialogPayload,
  StartDialogResponse,
  SubmitAnswerPayload
} from "../types";

function trimTrailingSlash(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, "");
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return (await response.json()) as T;
}

export async function startDialog(baseUrl: string, payload: StartDialogPayload): Promise<StartDialogResponse> {
  const url = `${trimTrailingSlash(baseUrl)}/dialogs/start`;
  return requestJson<StartDialogResponse>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function submitAnswer(baseUrl: string, payload: SubmitAnswerPayload): Promise<AnswerResponse> {
  const url = `${trimTrailingSlash(baseUrl)}/dialogs/answer`;
  return requestJson<AnswerResponse>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

export async function fetchDialogSnapshot(
  baseUrl: string,
  dialogId: string
): Promise<DialogSnapshotResponse> {
  const url = `${trimTrailingSlash(baseUrl)}/dialogs/${dialogId}`;
  return requestJson<DialogSnapshotResponse>(url);
}

export async function resetUserState(
  baseUrl: string,
  userId: string
): Promise<ResetUserStateResponse> {
  const url = `${trimTrailingSlash(baseUrl)}/users/${encodeURIComponent(userId)}/reset`;
  return requestJson<ResetUserStateResponse>(url, { method: "POST" });
}
