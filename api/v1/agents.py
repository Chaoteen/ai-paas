from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Any
import uuid
import re as regex
import json

from models.database import get_db
# 不再导入 Agent 模型，避免 ORM 冲突
# from schemas.agent import AgentCreate, AgentUpdate, AgentResponse 
# 由于 Schema 可能也不匹配，我们直接用 dict 接收或动态验证

router = APIRouter()

# 临时用户模拟 (匹配数据库中的真实 ID)
async def get_current_user():
    return type('User', (), {
        'id': '972f390d-50c8-4baa-a617-5d0c01f39efb', 
        'role': 'admin', 
        'organization_id': '65fc343d-1624-4729-b391-6fc6db64249e', 
        'auth_level': 'full', 
        'level': 'L5', 
        'mfa_verified': True
    })()

@router.post("/", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request_data: dict, # 直接接收 dict，避开 Schema 验证错误
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    from sqlalchemy import text
    
    # 1. 提取并验证必要字段
    name = request_data.get("name")
    model_name = request_data.get("model_name", "qwen-max")
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
        
    # 2. 准备数据
    slug_base = regex.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    unique_slug = f"{slug_base}-{str(uuid.uuid4())[:8]}"
    
    model_config = {
        "model_name": model_name,
        "temperature": request_data.get("temperature", 0.7),
        "max_tokens": request_data.get("max_tokens", 2048)
    }
    if request_data.get("system_prompt"):
        model_config['system_prompt'] = request_data["system_prompt"]
        
    # 硬编码 Project ID (测试用)
    target_project_id = "9dc5f322-2392-49a1-8455-2241afc1c4bb"
    
    agent_id = str(uuid.uuid4())
    allowed_roles = request_data.get("allowed_roles", ["owner", "admin"])
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
        
    sensitivity = request_data.get("sensitivity", "internal")
    requires_mfa = request_data.get("requires_mfa", False)
    description = request_data.get("description")

    # 3. 执行 Raw SQL (修复语法：移除 ::jsonb，Python 端 dumps)
    # 注意：SQLAlchemy text() 使用 :param 占位符。
    # PostgreSQL 会将传入的 JSON 字符串自动转换为 JSONB，无需显式转换。
    stmt = text("""
        INSERT INTO agents (model_name, 
            id, project_id, name, slug, description, agent_type, status,
            model_provider, model_config, system_prompt, workflow_definition,
            workflow_engine, enabled_tools, version, sensitivity, owner_id,
            tags, allowed_roles, requires_mfa, created_at, updated_at, is_deleted
        ) VALUES (
            :model_name, :id, :project_id, :name, :slug, :description, :agent_type, :status,
            :model_provider, :model_config, :system_prompt, :workflow_definition,
            :workflow_engine, :enabled_tools, :version, :sensitivity, :owner_id,
            :tags, :allowed_roles, :requires_mfa, NOW(), NOW(), false
        ) RETURNING id, name, slug, status, sensitivity, owner_id, project_id, created_at
    """)
    
    params = {
        "model_name": model_name,
        "id": agent_id,
        "project_id": target_project_id,
        "name": name,
        "slug": unique_slug,
        "description": description,
        "agent_type": "chat",
        "status": "active",
        "model_provider": "openai",
        "model_config": json.dumps(model_config), # Python 端转为 JSON 字符串
        "system_prompt": request_data.get("system_prompt"),
        "workflow_definition": None,
        "workflow_engine": None,
        "enabled_tools": [],
        "version": 1,
        "sensitivity": sensitivity,
        "owner_id": current_user.id,
        "tags": [],
        "allowed_roles": allowed_roles,
        "requires_mfa": requires_mfa
    }
    
    try:
        result = db.execute(stmt, params)
        db.commit()
        row = result.fetchone()
        if row:
            return dict(row._mapping)
        else:
            raise HTTPException(status_code=500, detail="Insert failed")
    except Exception as e:
        db.rollback()
        # 返回详细错误以便调试
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")

@router.get("/", response_model=List[dict])
async def list_agents(db: Session = Depends(get_db), current_user: Any = Depends(get_current_user)):
    from sqlalchemy import text
    stmt = text("SELECT id, name, slug, status, sensitivity, created_at FROM agents WHERE is_deleted = false LIMIT 100")
    result = db.execute(stmt)
    return [dict(row._mapping) for row in result.fetchall()]

@router.get("/{agent_id}", response_model=dict)
async def get_agent(agent_id: str, db: Session = Depends(get_db), current_user: Any = Depends(get_current_user)):
    from sqlalchemy import text
    stmt = text("SELECT * FROM agents WHERE id = :id AND is_deleted = false")
    result = db.execute(stmt, {"id": agent_id})
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    return dict(row._mapping)

@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: str, db: Session = Depends(get_db), current_user: Any = Depends(get_current_user)):
    from sqlalchemy import text
    stmt = text("UPDATE agents SET is_deleted = true, updated_at = NOW() WHERE id = :id")
    db.execute(stmt, {"id": agent_id})
    db.commit()
    return None

@router.put("/{agent_id}", response_model=dict)
async def update_agent(
    agent_id: str,
    request_data: dict,
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user)
):
    from sqlalchemy import text
    import json
    
    # 1. 检查 Agent 是否存在且未被删除
    check_stmt = text("SELECT id, model_config FROM agents WHERE id = :id AND is_deleted = false")
    result = db.execute(check_stmt, {"id": agent_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found or already deleted")
    
    existing_config = row._mapping['model_config'] or {}
    if isinstance(existing_config, str):
        existing_config = json.loads(existing_config)

    # 2. 构建动态更新字段
    updates = []
    params = {"id": agent_id}
    
    # 普通字段映射
    field_mapping = {
        "name": "name",
        "slug": "slug",
        "description": "description",
        "agent_type": "agent_type",
        "status": "status",
        "model_provider": "model_provider",
        "sensitivity": "sensitivity",
        "requires_mfa": "requires_mfa",
        "system_prompt": "system_prompt",
        "workflow_definition": "workflow_definition",
        "workflow_engine": "workflow_engine",
        "version": "version"
    }
    
    for input_key, db_col in field_mapping.items():
        if input_key in request_data:
            updates.append(f"{db_col} = :{input_key}")
            params[input_key] = request_data[input_key]
            
    # Array 类型字段
    for arr_field in ["tags", "allowed_roles", "enabled_tools"]:
        if arr_field in request_data:
            val = request_data[arr_field]
            if isinstance(val, str):
                val = [val]
            updates.append(f"{arr_field} = :{arr_field}")
            params[arr_field] = val
            
    # 特殊处理：model_name 和 model_config (JSONB)
    config_changed = False
    if "model_name" in request_data:
        updates.append("model_name = :model_name")
        params["model_name"] = request_data["model_name"]
        existing_config["model_name"] = request_data["model_name"]
        config_changed = True
        
    if "temperature" in request_data:
        existing_config["temperature"] = request_data["temperature"]
        config_changed = True
        
    if "max_tokens" in request_data:
        existing_config["max_tokens"] = request_data["max_tokens"]
        config_changed = True
        
    if config_changed:
        updates.append("model_config = :model_config_json")
        params["model_config_json"] = json.dumps(existing_config)

    if not updates:
        # 无有效更新，返回原数据
        get_stmt = text("SELECT * FROM agents WHERE id = :id")
        res = db.execute(get_stmt, {"id": agent_id})
        return dict(res.fetchone()._mapping)

    # 3. 执行更新
    updates.append("updated_at = NOW()")
    set_clause = ", ".join(updates)
    
    sql = f"""
        UPDATE agents 
        SET {set_clause} 
        WHERE id = :id 
        RETURNING id, name, slug, status, sensitivity, owner_id, project_id, updated_at
    """
    
    stmt = text(sql)
    try:
        result = db.execute(stmt, params)
        db.commit()
        row = result.fetchone()
        if row:
            return dict(row._mapping)
        else:
            raise HTTPException(status_code=500, detail="Update failed")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"DB Error: {str(e)}")
