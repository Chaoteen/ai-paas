import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import type { MenuItem } from '../api/bootstrap';

// 内部子组件：渲染单个菜单项
function MenuNode({ item }: { item: MenuItem }) {
  const navigate = useNavigate();
  const location = useLocation();
  
  const isActive = location.pathname === item.route;

  if (!item.route) {
    return <div style={{ padding: '12px 15px', color: '#ccc' }}>{item.title}</div>;
  }

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault(); // 阻止默认行为
    e.stopPropagation(); // 阻止冒泡
    console.log(`🔥 [SIDEBAR CLICK] 正在跳转: ${item.title} -> ${item.route}`);
    navigate(item.route);
  };

  return (
    <div
      onClick={handleClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '14px 16px',
        marginBottom: '8px',
        borderRadius: '8px',
        cursor: 'pointer',
        userSelect: 'none',
        transition: 'background 0.2s',
        backgroundColor: isActive ? '#eff6ff' : 'transparent',
        color: isActive ? '#1d4ed8' : '#374151',
        fontWeight: isActive ? '600' : '500',
        borderLeft: isActive ? '4px solid #1d4ed8' : '4px solid transparent',
        fontSize: '15px'
      }}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = '#f3f4f6';
      }}
      onMouseLeave={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
      }}
    >
      {/* 图标处理：如果是英文单词（图标名），则隐藏不显示，避免显示 "Terminal" 这种文字 */}
      {item.icon && item.icon.length > 10 ? null : (
        <span style={{ marginRight: '12px', fontSize: '18px', display: 'flex', alignItems: 'center' }}>
           {/* 这里暂时留空，或者您可以后续接入真实的图标库，目前先隐藏以免显示乱码文字 */}
           {/* 如果想显示一个通用图标，可以取消下面这行的注释 */}
           {/* 📌 */} 
        </span>
      )}
      
      <span>{item.title}</span>
    </div>
  );
}

// 主侧边栏组件
export function Sidebar({ menus }: { menus: MenuItem[] }) {
  return (
    <div
      style={{
        width: '260px',
        height: '100vh', // 强制占满视口高度
        backgroundColor: '#ffffff',
        borderRight: '1px solid #e5e7eb',
        padding: '20px 10px',
        display: 'flex',
        flexDirection: 'column',
        
        // 🔥🔥🔥 关键修复：强制提升层级，防止被遮挡 🔥🔥🔥
        position: 'relative',
        zIndex: 9999, 
        pointerEvents: 'auto',
        overflowY: 'auto',
        boxShadow: '2px 0 8px rgba(0,0,0,0.05)' // 加一点阴影确保它在视觉上浮起
      }}
    >
      {/* 品牌区域 */}
      <div style={{ padding: '0 15px 25px 15px', borderBottom: '1px solid #f3f4f6', marginBottom: '15px' }}>
        <h1 style={{ fontSize: '22px', fontWeight: '800', color: '#111827', margin: 0, letterSpacing: '-0.5px' }}>
          AI-PaaS V4
        </h1>
        <p style={{ fontSize: '12px', color: '#6b7280', margin: '5px 0 0 0', textTransform: 'uppercase', letterSpacing: '1px' }}>
          Platform
        </p>
      </div>

      {/* 菜单列表 */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {menus && menus.length > 0 ? (
          menus.map((m) => (
            <MenuNode key={m.id} item={m} />
          ))
        ) : (
          <div style={{ padding: 20, color: '#999', textAlign: 'center', fontSize: '13px' }}>
            加载菜单中...
          </div>
        )}
      </div>
      
      {/* 底部信息 */}
      <div style={{ padding: '15px', fontSize: '11px', color: '#9ca3af', textAlign: 'center', borderTop: '1px solid #f3f4f6', marginTop: 'auto' }}>
        Build v1.0.0
      </div>
    </div>
  );
}