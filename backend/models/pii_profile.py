"""
PII Profile Model
=================

User-defined PII redaction profiles. Each profile captures:
  - A blocklist of literal terms always redacted (e.g. internal project names)
  - An allowlist of terms never redacted (e.g. company name that could match
    a built-in name detector)
  - Custom PII types with trigger phrases + value patterns
  - Which built-in types to enable (subset of pii_tool.ALL_PII_TYPES)

Profiles are scoped to a project via project_id. NULL project_id means
global / available to all projects.
"""

import datetime
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from db.database import Base


class PIIProfile(Base):
    """A named collection of PII redaction rules."""

    __tablename__ = "pii_profiles"

    id = Column(Integer, primary_key=True, index=True)

    # Project scoping (NULL = global / available to all projects)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)

    # Profile metadata
    name = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Rule sets (all JSON for flexibility — validated at application layer)
    #
    # blocklist: ["ProjectAthena", "ClientXYZ"] — these literal terms are
    # always redacted as [REDACTED_CUSTOM] regardless of other rules.
    blocklist = Column(JSON, nullable=False, default=list)

    # allowlist: ["Example Company"] — these terms are never redacted even
    # if another detector would flag them (for example, a company name).
    allowlist = Column(JSON, nullable=False, default=list)

    # custom_types: [{ "name": "internal_id", "trigger_phrases": ["employee ID"], "value_regex": "EMP-\\d+" }]
    custom_types = Column(JSON, nullable=False, default=list)

    # enabled_builtin_types: override the default ALL_PII_TYPES list.
    # Empty list = use all built-in types. Specific list = only those types.
    enabled_builtin_types = Column(JSON, nullable=False, default=list)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Relationships
    project = relationship("Project", foreign_keys=[project_id])
