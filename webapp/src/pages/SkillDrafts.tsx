import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listSkillDrafts, SkillDraft } from "../api/skillDistillation";

export default function SkillDrafts() {
  const [status, setStatus] = useState("");
  const [items, setItems] = useState<SkillDraft[]>([]);
  const [err, setErr] = useState("");

  async function load() {
    try {
      setErr("");
      const body = await listSkillDrafts(status || undefined);
      setItems(body.items);
    } catch (e) {
      setErr(String(e));
    }
  }

  useEffect(() => {
    void load();
  }, [status]);

  return (
    <div style={{ padding: 24 }}>
      <h1>Skill Drafts</h1>
      <p>阶段1首版草稿库：按状态查看候选技能草稿。</p>
      {err ? <div style={{ color: "red" }}>{err}</div> : null}
      <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ marginBottom: 16 }}>
        <option value="">all</option>
        <option value="draft">draft</option>
        <option value="reviewing">reviewing</option>
        <option value="accepted">accepted</option>
        <option value="rejected">rejected</option>
        <option value="archived">archived</option>
      </select>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th align="left">name</th>
            <th align="left">draft_key</th>
            <th align="left">version</th>
            <th align="left">status</th>
            <th align="left">detail</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.skill_draft_id}>
              <td>{item.name}</td>
              <td>{item.draft_key}</td>
              <td>{item.draft_version}</td>
              <td>{item.status}</td>
              <td>
                <Link to={`/skills/library/${item.skill_draft_id}`}>View</Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}