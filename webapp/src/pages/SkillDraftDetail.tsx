import React, { useEffect, useState } from "react";
    try {
      const body = await getSkillDraft(skillDraftId);
      setItem(body);
      setName(body.name);
      setIntentSummary(body.intent_summary || "");
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => {
    void load();
  }, [skillDraftId]);

  if (!skillDraftId) {
    return (
      <div style={{ padding: 24 }}>
        <h1>Create Skill Draft</h1>
        {err ? <div style={{ color: "red" }}>{err}</div> : null}
        <input value={draftKey} onChange={(e) => setDraftKey(e.target.value)} placeholder="draft_key" style={{ display: "block", marginBottom: 8 }} />
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="name" style={{ display: "block", marginBottom: 8 }} />
        <input value={recordingSessionId} onChange={(e) => setRecordingSessionId(e.target.value)} placeholder="recording_session_id (optional)" style={{ display: "block", marginBottom: 8, width: 360 }} />
        <textarea value={intentSummary} onChange={(e) => setIntentSummary(e.target.value)} rows={4} style={{ display: "block", width: 520, marginBottom: 12 }} />
        <button
          onClick={async () => {
            try {
              const created = await createSkillDraft({
                recording_session_id: recordingSessionId || null,
                draft_key: draftKey,
                name,
                intent_summary: intentSummary,
                distillation_source_type: recordingSessionId ? "dialogue" : "imported",
                input_schema_json: {},
                output_schema_json: {},
                draft_definition_json: {},
                distillation_notes_json: {},
                execution_binding_json: DEFAULT_BINDING,
                derived_from_json: {},
                metadata_json: {},
              });
              window.location.href = `/skills/library/${created.skill_draft_id}`;
            } catch (e) {
              setErr(String(e));
            }
          }}
        >
          Create Draft
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: 24 }}>
      <h1>Skill Draft Detail</h1>
      {err ? <div style={{ color: "red" }}>{err}</div> : null}
      {!item ? (
        <div>Loading...</div>
      ) : (
        <>
          <div style={{ marginBottom: 8 }}>ID: {item.skill_draft_id}</div>
          <div style={{ marginBottom: 8 }}>draft_key: {item.draft_key}</div>
          <div style={{ marginBottom: 8 }}>draft_version: {item.draft_version}</div>
          <div style={{ marginBottom: 8 }}>status: {item.status}</div>

          <input value={name} onChange={(e) => setName(e.target.value)} style={{ display: "block", marginBottom: 8, width: 360 }} />
          <textarea value={intentSummary} onChange={(e) => setIntentSummary(e.target.value)} rows={6} style={{ display: "block", width: 520, marginBottom: 12 }} />

          <button
            onClick={async () => {
              await patchSkillDraft(item.skill_draft_id, {
                name,
                intent_summary: intentSummary,
              });
              await load();
            }}
            style={{ marginRight: 8 }}
          >
            Save
          </button>

          <button onClick={async () => { await transitionSkillDraft(item.skill_draft_id, "submit-review"); await load(); }} style={{ marginRight: 8 }}>submit-review</button>
          <button onClick={async () => { await transitionSkillDraft(item.skill_draft_id, "accept"); await load(); }} style={{ marginRight: 8 }}>accept</button>
          <button onClick={async () => { await transitionSkillDraft(item.skill_draft_id, "reject"); await load(); }} style={{ marginRight: 8 }}>reject</button>
          <button onClick={async () => { await transitionSkillDraft(item.skill_draft_id, "archive"); await load(); }}>archive</button>
        </>
      )}
    </div>
  );
}