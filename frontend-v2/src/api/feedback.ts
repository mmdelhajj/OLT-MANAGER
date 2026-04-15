import { api } from "./client";

export type FeedbackCategory = "bug" | "idea" | "praise" | "other";

export interface FeedbackPayload {
  category: FeedbackCategory;
  message: string;
  page_url?: string;
}

export interface FeedbackEntry {
  id: string;
  category: FeedbackCategory;
  message: string;
  page_url: string | null;
  created_at: string;
}

export async function submitFeedback(payload: FeedbackPayload) {
  const { data } = await api.post<FeedbackEntry>("/api/feedback", payload);
  return data;
}

export async function listMyFeedback() {
  const { data } = await api.get<FeedbackEntry[]>("/api/feedback");
  return data;
}
