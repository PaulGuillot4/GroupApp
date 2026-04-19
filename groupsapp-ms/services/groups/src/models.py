from sqlalchemy import MetaData, Table, Column, String, DateTime, func

metadata = MetaData()

groups = Table(
    "groups",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("description", String(1024), nullable=False, server_default=""),
    Column("owner_id", String(36), nullable=False),
    Column("subscription_type", String(50), nullable=False, server_default="free"),
    Column("avatar_url", String(512), nullable=False, server_default=""),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

channels = Table(
    "channels",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("group_id", String(36), nullable=False),
    Column("name", String(255), nullable=False),
    Column("description", String(1024), nullable=False, server_default=""),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)

group_members = Table(
    "group_members",
    metadata,
    Column("user_id", String(36), primary_key=True, nullable=False),
    Column("group_id", String(36), primary_key=True, nullable=False),
    Column("role", String(50), nullable=False, server_default="member"),
    Column("joined_at", DateTime(timezone=True), server_default=func.now()),
)
