from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0001_initial"),
    ]
    operations = [
        migrations.AddField(
            model_name="message",
            name="sender_username",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
