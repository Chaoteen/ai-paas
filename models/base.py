"""
AI-PaaS 数据模型基类配置
SQLAlchemy 2.0 + Async Support + PostgreSQL
"""
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean, Column, DateTime, Index, Integer, String, Text, 
    ForeignKey, UniqueConstraint, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY, TIMESTAMP
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship, 
    validates, declared_attr
)
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """所有模型的基类"""
    
    # 通用字段
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=lambda: uuid4()
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="软删除标记"
    )
    
    @declared_attr
    def __tablename__(cls) -> str:
        """自动生成表名（复数形式）"""
        name = cls.__name__
        # 简单复数转换规则
        if name.endswith('y'):
            return name[:-1] + 'ies'
        elif name.endswith('s'):
            return name + 'es'
        else:
            return name + 's'
    
    def to_dict(self, exclude: Optional[list] = None) -> dict[str, Any]:
        """转换为字典（排除敏感字段）"""
        exclude = exclude or ['password_hash', 'api_key_hash']
        return {
            c.name: getattr(self, c.name)
            for c in self.__table__.columns
            if c.name not in exclude
        }