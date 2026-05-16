from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.analysis import LeadAnalysis


class LeadStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SENT_TO_BITRIX = "sent_to_bitrix"


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_status_created_at", "status", "created_at"),
        {"schema": "leads"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    redrive_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    company_name: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    instagram: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(Text)
    segment: Mapped[str | None] = mapped_column(Text)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=LeadStatus.PENDING.value, server_default=LeadStatus.PENDING.value
    )
    bitrix_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    analysis: Mapped[LeadAnalysis | None] = relationship(
        "LeadAnalysis", back_populates="lead", uselist=False, cascade="all, delete-orphan"
    )
