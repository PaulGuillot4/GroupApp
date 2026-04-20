from sqlalchemy import MetaData, Table, Column, String, BigInteger, DateTime, func

metadata = MetaData()

files = Table(
    "files",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("owner_id", String(36), nullable=False),
    Column("url", String(512), nullable=False),
    Column("mime_type", String(128), nullable=False, server_default="application/octet-stream"),
    Column("size", BigInteger, nullable=False, server_default="0"),
    Column("uploaded_at", DateTime(timezone=True), server_default=func.now()),
)
