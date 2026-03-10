export type StartDialogResponse = {
  dialog_id: string;
  current_round: number;
  max_round: number;
  current_question: string;
  current_concept: string;
  knowledge_graph_root: Record<string, unknown>;
};

export type AnswerResponse = {
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

export type DialogSnapshotResponse = {
  dialog_id: string;
  created_at: string;
  updated_at: string;
  finished: boolean;
  state: Record<string, unknown>;
};

export type StartDialogPayload = {
  question: string;
  max_round: number;
  auto_answer_enabled: boolean;
  auto_answer_proficiency: number;
  question_mode: "open" | "choice";
  choice_option_count: 2 | 3 | 4;
};

export type SubmitAnswerPayload = {
  dialog_id: string;
  user_answer: string;
};


