import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";

import Chat from "../pages/chat";
import { Admin } from "../pages/Admin";
import { PluginPage } from "../pages/Plugin";
import { OpaConsole } from "../pages/OpaConsole";

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/chat" replace />} />
      <Route path="/chat" element={<Chat />} />
      <Route path="/admin" element={<Admin />} />
      <Route path="/opa" element={<OpaConsole />} />
      {/* iframe-first plugin host */}
      <Route path="/plugin" element={<PluginPage />} />

      {/* fallback */}
      <Route path="*" element={<Navigate to="/chat" replace />} />
          <Route path="/plugins/:pluginId" element={<PluginPage />} />
    </Routes>
  );
}
