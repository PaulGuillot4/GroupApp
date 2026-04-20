from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.RunSQL("CREATE SCHEMA IF NOT EXISTS messaging"),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("sender_id", models.CharField(max_length=36)),
                ("type", models.CharField(max_length=20)),
                ("group_id", models.CharField(blank=True, default="", max_length=36)),
                ("channel_id", models.CharField(blank=True, default="", max_length=36)),
                ("receiver_id", models.CharField(blank=True, default="", max_length=36)),
                ("content", models.TextField(blank=True, default="")),
                ("message_type", models.CharField(default="text", max_length=20)),
                ("file_url", models.CharField(blank=True, default="", max_length=512)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"app_label": "chat", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="MessageStatus",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("message", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="statuses", to="chat.message")),
                ("user_id", models.CharField(max_length=36)),
                ("status", models.CharField(default="sent", max_length=20)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"app_label": "chat", "unique_together": {("message", "user_id")}},
        ),
    ]
