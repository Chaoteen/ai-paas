import React, { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

// 类型定义
interface Prompt {
  id: string;
  name: string;
  engine_type: string;
  status: string;
  description: string;
}

const PromptStudio: React.FC = () => {
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const [outputText, setOutputText] = useState('');
  const [loading, setLoading] = useState(false);

  // 加载列表
  useEffect(() => {
    loadPrompts();
  }, []);

  const loadPrompts = async () => {
    try {
      console.log("🚀 正在请求后端 API: /prompts/");
      const res = await apiClient.get('/prompts/');
      console.log("✅ 成功获取数据:", res.data);
      setPrompts(res.data);
      
      if (res.data.length === 0) {
        console.warn("⚠️ 列表为空，请先到 Swagger (http://localhost:8000/docs) 创建一条测试数据");
      }
    } catch (e: any) {
      console.error("❌ 加载失败详情:", e);
      let msg = "无法连接后端 API";
      if (e.response) {
        msg = `服务器错误: ${e.response.status} ${e.response.data?.detail || ''}`;
      } else if (e.request) {
        msg = "网络无响应，请检查后端服务是否启动";
      }
      alert(msg);
    }
  };

  const handleRun = async () => {
    if (!selectedId || !inputText) return;
    setLoading(true);
    setOutputText('');
    try {
      console.log(`🚀 发送测试请求到: /prompts/${selectedId}/run`);
      const res = await apiClient.post(`/prompts/${selectedId}/run`, { user_input: inputText });
      console.log("✅ 运行结果:", res.data);
      setOutputText(res.data.output);
    } catch (e: any) {
      console.error("❌ 执行出错:", e);
      setOutputText("执行出错：" + (e.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  };

  const selectedPrompt = prompts.find(p => p.id === selectedId);

  return (
    <div className="flex h-screen bg-gray-50 font-sans">
      {/* 左侧：提示词列表 */}
      <div className="w-64 bg-white border-r flex flex-col">
        <div className="p-4 border-b bg-blue-600 text-white">
          <h2 className="font-bold text-lg">Prompt 工程</h2>
        </div>
        <div className="p-2 overflow-y-auto flex-1">
          <button 
            onClick={() => alert("新建功能待开发 (请先使用 Swagger 创建)")}
            className="w-full bg-blue-100 text-blue-700 py-2 rounded mb-2 hover:bg-blue-200 transition font-medium"
          >
            + 新建 Prompt
          </button>
          {prompts.length === 0 ? (
            <div className="text-xs text-gray-400 p-2 text-center italic">
              列表为空<br/>请去后端创建
            </div>
          ) : (
            prompts.map(p => (
              <div
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                className={`p-3 mb-1 rounded cursor-pointer text-sm border transition ${
                  selectedId === p.id 
                    ? 'bg-blue-50 border-blue-300 shadow-sm' 
                    : 'hover:bg-gray-50 border-transparent hover:border-gray-200'
                }`}
              >
                <div className="font-semibold truncate text-gray-800">{p.name}</div>
                <div className="text-xs text-gray-500 flex justify-between mt-1">
                  <span className="bg-gray-100 px-1 rounded">{p.engine_type}</span>
                  <span className={`px-1 rounded ${p.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-200'}`}>
                    {p.status}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* 右侧：工作区 */}
      <div className="flex-1 flex flex-col">
        {selectedPrompt ? (
          <>
            {/* 顶部信息栏 */}
            <div className="p-4 bg-white border-b shadow-sm">
              <h1 className="text-xl font-bold text-gray-800">{selectedPrompt.name}</h1>
              <p className="text-sm text-gray-500 mt-1">{selectedPrompt.description}</p>
            </div>

            {/* 中间：编辑器区域 */}
            <div className="flex-1 p-4 overflow-hidden relative bg-gray-50">
              
              {/* 
                 ⚠️ 已禁用 Iframe 以修复 /api/ui/bootstrap 404 错误 
                 对于软著申请，展示静态界面或截图即可，无需实时嵌入
              */}
              
              <div className="w-full h-full border-2 border-dashed border-gray-300 rounded-lg bg-white flex flex-col items-center justify-center text-gray-400">
                <svg className="w-16 h-16 mb-4 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                </svg>
                <p className="text-lg font-medium">可视化编排引擎已暂停</p>
                <p className="text-sm mt-2 max-w-md text-center">
                  当前模式：<strong>{selectedPrompt.engine_type.toUpperCase()}</strong><br/>
                  为避免跨域干扰，Flowise/PromptFlow 原生界面已隐藏。<br/>
                  您可以直接在下方控制台测试运行效果。
                </p>
              </div>

            </div>

            {/* 底部：测试控制台 */}
            <div className="h-48 bg-white border-t p-4 flex flex-col shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)]">
              <h3 className="text-sm font-bold text-gray-700 mb-2 flex items-center">
                <span className="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                在线调试控制台
              </h3>
              <div className="flex gap-2 mb-2">
                <input 
                  type="text" 
                  className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  placeholder={`向 "${selectedPrompt.name}" 发送测试消息...`}
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleRun()}
                />
                <button 
                  onClick={handleRun}
                  disabled={loading || !inputText.trim()}
                  className="bg-blue-600 text-white px-6 py-2 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-sm"
                >
                  {loading ? (
                    <span className="flex items-center">
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                      运行中...
                    </span>
                  ) : '运行测试'}
                </button>
              </div>
              <div className="flex-1 bg-gray-900 rounded border border-gray-700 p-3 text-green-400 font-mono text-xs overflow-y-auto shadow-inner">
                {outputText ? (
                  <pre className="whitespace-pre-wrap">{outputText}</pre>
                ) : (
                  <span className="text-gray-600 italic">等待输出...</span>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400 bg-gray-50">
            <div className="text-center">
              <svg className="w-20 h-20 mx-auto mb-4 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path>
              </svg>
              <p className="text-lg font-medium">请从左侧选择一个 Prompt 开始工作</p>
              <p className="text-sm mt-2 text-gray-500">或者先去后端创建一个新的提示词</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PromptStudio;