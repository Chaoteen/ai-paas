export type WorkflowExecution = {
  workflow_execution_id: string;
  task_id: string;
  tenant_id: string;
  workflow_key: string;
  workflow_version: string;
  status: string;
  definition_snapshot_json: Record<string, unknown>;
  input_json: Record<string, unknown>;
  context_json: Record<string, unknown>;
  system_context_json: Record<string, unknown>;
  output_json?: Record<string, unknown> | null;
  error_text?: string | null;
  active_node_ids: string[];
  resolved_capabilities_json: Record<string, unknown>;
  governance_json: Record<string, unknown>;
  trace_json: Record<string, unknown>;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at: string;
};

export type WorkflowExecutionListResponse = {
  items: WorkflowExecution[];
  total: number;
};

export type WorkflowStepExecution = {
  workflow_step_execution_id: string;
  workflow_execution_id: string;
  node_id: string;
  node_type: string;
  capability_ref_json: Record<string, unknown>;
  status: string;
  attempt_no: number;
  input_json: Record<string, unknown>;
  output_json?: Record<string, unknown> | null;
  error_text?: string | null;
  retry_policy_json: Record<string, unknown>;
  timeout_policy_json: Record<string, unknown>;
  compensation_policy_json: Record<string, unknown>;
  trace_json: Record<string, unknown>;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at: string;
};

export type WorkflowExecutionStepsResponse = {
  items: WorkflowStepExecution[];
  total: number;
};

export type WorkflowExecutionEvent = {
  workflow_execution_event_id: number;
  workflow_execution_id: string;
  workflow_step_execution_id?: string | null;
  tenant_id: string;
  event_type: string;
  payload_json: Record<string, unknown>;
  created_at: string;
};

export type WorkflowExecutionEventsResponse = {
  items: WorkflowExecutionEvent[];
  total: number;
};

export type WorkflowExecutionTimelineItem = {
  sequence_no: number;
  created_at: string;
  lane: string;
  event_type: string;
  workflow_step_execution_id?: string | null;
  node_id?: string | null;
  status?: string | null;
  payload_json: Record<string, unknown>;
};

export type WorkflowExecutionTimelineResponse = {
  workflow_execution_id: string;
  items: WorkflowExecutionTimelineItem[];
  total: number;
};

export type WorkflowExecutionDetailResponse = {
  execution: WorkflowExecution;
  steps: WorkflowStepExecution[];
  events: WorkflowExecutionEvent[];
  timeline: WorkflowExecutionTimelineItem[];
  summary: {
    workflow_execution_id: string;
    task_id: string;
    tenant_id: string;
    workflow_key: string;
    workflow_version: string;
    execution_status: string;
    step_count: number;
    event_count: number;
    active_node_ids: string[];
    has_error: boolean;
  };
};

function getToken(): string {
  return (localStorage.getItem("AI_PAAS_TOKEN") || "").trim();
}

function getHeaders(): HeadersInit {
  const token = getToken();
  if (!token) {
    throw new Error("Missing token: localStorage.AI_PAAS_TOKEN is empty");
  }
  return {
    Authorization: `Bearer ${token}`,
  };
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    method: "GET",
    headers: getHeaders(),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`request failed: ${response.status} ${text}`);
  }

  return (await response.json()) as T;
}

export async function listWorkflowExecutions(
  tenantId: string,
): Promise<WorkflowExecutionListResponse> {
  const qs = new URLSearchParams({ tenant_id: tenantId });
  return getJson<WorkflowExecutionListResponse>(`/api/v1/workflow/executions?${qs.toString()}`);
}

export async function getWorkflowExecution(
  workflowExecutionId: string,
): Promise<WorkflowExecution> {
  return getJson<WorkflowExecution>(`/api/v1/workflow/executions/${workflowExecutionId}`);
}

export async function getWorkflowExecutionDetail(
  workflowExecutionId: string,
): Promise<WorkflowExecutionDetailResponse> {
  return getJson<WorkflowExecutionDetailResponse>(
    `/api/v1/workflow/executions/${workflowExecutionId}/detail`,
  );
}

export async function listWorkflowExecutionSteps(
  workflowExecutionId: string,
): Promise<WorkflowExecutionStepsResponse> {
  return getJson<WorkflowExecutionStepsResponse>(
    `/api/v1/workflow/executions/${workflowExecutionId}/steps`,
  );
}

export async function listWorkflowExecutionEvents(
  workflowExecutionId: string,
): Promise<WorkflowExecutionEventsResponse> {
  return getJson<WorkflowExecutionEventsResponse>(
    `/api/v1/workflow/executions/${workflowExecutionId}/events`,
  );
}

export async function getWorkflowExecutionTimeline(
  workflowExecutionId: string,
): Promise<WorkflowExecutionTimelineResponse> {
  return getJson<WorkflowExecutionTimelineResponse>(
    `/api/v1/workflow/executions/${workflowExecutionId}/timeline`,
  );
}