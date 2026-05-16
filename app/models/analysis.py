from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.lead import Lead


class LeadAnalysis(Base):
    __tablename__ = "lead_analysis"
    __table_args__ = ({"schema": "leads"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("leads.leads.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    site_active: Mapped[bool | None] = mapped_column(Boolean)
    has_whatsapp: Mapped[bool | None] = mapped_column(Boolean)
    has_form: Mapped[bool | None] = mapped_column(Boolean)
    has_meta_pixel: Mapped[bool | None] = mapped_column(Boolean)
    has_google_tag: Mapped[bool | None] = mapped_column(Boolean)
    has_gtm: Mapped[bool | None] = mapped_column(Boolean)

    instagram_active: Mapped[bool | None] = mapped_column(Boolean)
    last_post_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    posting_frequency: Mapped[str | None] = mapped_column(Text)
    best_post_url: Mapped[str | None] = mapped_column(Text)
    best_post_likes: Mapped[int | None] = mapped_column(Integer)
    best_post_comments: Mapped[int | None] = mapped_column(Integer)

    has_meta_ads: Mapped[bool | None] = mapped_column(Boolean)
    has_google_ads: Mapped[bool | None] = mapped_column(Boolean)
    meta_ads_print: Mapped[str | None] = mapped_column(Text)
    google_ads_print: Mapped[str | None] = mapped_column(Text)

    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_pains: Mapped[str | None] = mapped_column(Text)
    ai_opportunity: Mapped[str | None] = mapped_column(Text)
    ai_message: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer)

    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    lead: Mapped[Lead] = relationship("Lead", back_populates="analysis")
