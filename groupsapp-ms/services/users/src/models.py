from sqlalchemy import MetaData, Table, Column, String, DateTime

metadata = MetaData()

user_profiles = Table(
    "user_profiles",
    metadata,
    Column("user_id", String(36), primary_key=True),
    Column("avatar_url", String(512), nullable=False, server_default=""),
    Column("bio", String(512), nullable=False, server_default=""),
    Column("last_seen", DateTime(timezone=True), nullable=True),
)
