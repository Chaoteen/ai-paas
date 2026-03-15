import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";

// --- 原有导入 ---
import { AbacTester } from "../pages/AbacTester";
import Chat from "../pages/chat";
import { Admin } from "../pages/Admin";
import { PluginPage } from "../pages/Plugin";
import { OpaConsole } from "../pages/OpaConsole";

// --- 👇 新增导入：我们刚开发的页面 👇 ---
import PromptStudio from "../pages/PromptStudio";
// 如果您还没创建这些文件，请先创建简单的占位文件，或者暂时注释掉这几行
// 见下方的“重要提示”
import AgentHub from "../pages/AgentHub"; 
import KnowledgeBase from "../pages/KnowledgeBase";
import Settings from "../pages/Settings";

export function AppRouter() {
  return (
    <Routes>
      {/* 1. 默认首页：重定向到 /prompts (而不是 /chat) */}
      <Route path="/" element={<Navigate to="/prompts" replace />} />

      {/* 2. 原有路由 (保留) */}
      <Route path="/chat" element={<Chat />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="/opa" element={<OpaConsole />} />
      <Route path="/abac" element={<AbacTester />} />
      <Route path="/plugin" element={<PluginPage />} />

      {/* 3. 👇 新增路由：对应 Bootstrap 返回的菜单 👇 */}
      <Route path="/prompts" element={<PromptStudio />} />
      <Route path="/agents" element={<AgentHub />} />
      <Route path="/knowledge" element={<KnowledgeBase />} />
      <Route path="/settings" element={<Settings />} />

      {/* 4. Fallback: 未知路径重定向到 /prompts */}
      <Route path="*" element={<Navigate to="/prompts" replace />} />
    </Routes>
  );
}