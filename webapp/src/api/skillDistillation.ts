import { apiClient } from "./client";

export type SkillDraft = {
  skill_draft_id: string;
  tenant_id: string;
  recording_session_id?: string | null;
  draft_key: string;
  draft_version: string;
  status: string;
  name: string;
  intent_summary?: string | null;
  distillation_source_type: string;
  input_schema_json: Record<string, unknown>;
  output_schema_json: Record<string, unknown>;
  draft_definition_json: Record<string, unknown>;
  distillation_notes_json: Record<string, unknown>;
  execution_binding_json: Record<string, unknown>;
  derived_from_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export async function createRecordingSession(payload: Record<string, unknown>) {
  const response = await apiClient.post<RecordingSession>("/recording/sessions", payload);
  return response.data;
}

export async function listRecordingSessions(status?: string) {
  const response = await apiClient.get<{ items: RecordingSession[] }>("/recording/sessions", {
    params: status ? { status } : {},
  });
  return response.data;
}

export async function getRecordingSession(id: string) {
  const response = await apiClient.get<RecordingSession>(`/recording/sessions/${id}`);
  return response.data;
}

export async function patchRecordingSession(id: string, payload: Record<string, unknown>) {
  const response = await apiClient.patch<RecordingSession>(`/recording/sessions/${id}`, payload);
  return response.data;
}

export async function appendRecordingEvent(id: string, payload: Record<string, unknown>) {
  const response = await apiClient.post<RecordingActionEvent>(`/recording/sessions/${id}/events`, payload);
  return response.data;
}

export async function listRecordingEvents(id: string) {
  const response = await apiClient.get<{ items: RecordingActionEvent[] }>(`/recording/sessions/${id}/events`);
  return response.data;
}

export async function transitionRecordingSession(id: string, action: string) {
  const response = await apiClient.post<RecordingSession>(`/recording/sessions/${id}/${action}`);
  return response.data;
}

export async function createSkillDraft(payload: Record<string, unknown>) {
  const response = await apiClient.post<SkillDraft>("/skill-drafts", payload);
  return response.data;
}

export async function listSkillDrafts(status?: string) {
  const response = await apiClient.get<{ items: SkillDraft[] }>("/skill-drafts", {
    params: status ? { status } : {},
  });
  return response.data;
}

export async function getSkillDraft(id: string) {
  const response = await apiClient.get<SkillDraft>(`/skill-drafts/${id}`);
  return response.data;
}

export async function patchSkillDraft(id: string, payload: Record<string, unknown>) {
  const response = await apiClient.patch<SkillDraft>(`/skill-drafts/${id}`, payload);
  return response.data;
}

export async function transitionSkillDraft(id: string, action: string) {
  const response = await apiClient.post<SkillDraft>(`/skill-drafts/${id}/${action}`);
  return response.data;
}