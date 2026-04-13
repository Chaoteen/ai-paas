import React, { useEffect, useState } from "react";
        </button>
      </section>

      <section style={{ marginBottom: 24 }}>
        <h2>Session 列表</h2>
        <ul>
          {sessions.map((item) => (
            <li key={item.recording_session_id}>
              <button onClick={() => setSelectedSessionId(item.recording_session_id)}>
                {item.title} / {item.status} / {item.source_type}
              </button>
            </li>
          ))}
        </ul>
      </section>

      {selectedSessionId ? (
        <section style={{ marginBottom: 24 }}>
          <h2>当前 Session</h2>
          <div style={{ marginBottom: 12 }}>ID: {selectedSessionId}</div>
          <button onClick={async () => { await transitionRecordingSession(selectedSessionId, "start-collecting"); await refreshSessions(); }} style={{ marginRight: 8 }}>start-collecting</button>
          <button onClick={async () => { await transitionRecordingSession(selectedSessionId, "mark-distilled"); await refreshSessions(); }} style={{ marginRight: 8 }}>mark-distilled</button>
          <button onClick={async () => { await transitionRecordingSession(selectedSessionId, "archive"); await refreshSessions(); }}>archive</button>
        </section>
      ) : null}

      {selectedSessionId ? (
        <section style={{ marginBottom: 24 }}>
          <h2>追加 Event</h2>
          <select value={eventType} onChange={(e) => setEventType(e.target.value)} style={{ marginRight: 8 }}>
            <option value="dialogue_step">dialogue_step</option>
            <option value="ui_action">ui_action</option>
            <option value="system_inference">system_inference</option>
          </select>
          <select value={actorType} onChange={(e) => setActorType(e.target.value)} style={{ marginRight: 8 }}>
            <option value="user">user</option>
            <option value="assistant">assistant</option>
            <option value="recorder">recorder</option>
            <option value="system">system</option>
          </select>
          <textarea value={payloadText} onChange={(e) => setPayloadText(e.target.value)} rows={6} style={{ display: "block", width: 520, margin: "12px 0" }} />
          <button
            onClick={async () => {
              try {
                setErr("");
                await appendRecordingEvent(selectedSessionId, {
                  idempotency_key: `manual-${Date.now()}`,
                  event_type: eventType,
                  actor_type: actorType,
                  payload_json: JSON.parse(payloadText),
                  source_ref_json: {},
                  metadata_json: {},
                });
                await refreshEvents(selectedSessionId);
              } catch (e) {
                setErr(String(e));
              }
            }}
          >
            Append Event
          </button>
        </section>
      ) : null}

      <section>
        <h2>Event 列表</h2>
        {events.length === 0 ? <div>No events</div> : null}
        <ul>
          {events.map((item) => (
            <li key={item.recording_action_event_id}>
              #{item.sequence_no} / {item.event_type} / {item.actor_type} / {JSON.stringify(item.payload_json)}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}