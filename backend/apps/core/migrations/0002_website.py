# Generated migration for Website model
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Website",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=255, blank=True, help_text='Optional display name for the website'),
                ),
                (
                    "domain",
                    models.CharField(max_length=255, help_text='Primary domain or host for this website (e.g. example.com)'),
                ),
                (
                    "url",
                    models.URLField(blank=True, null=True, help_text='Optional full URL (e.g. https://example.com)'),
                ),
                ("is_primary", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="websites",
                        to="core.organization",
                    ),
                ),
            ],
            options={
                "db_table": "websites",
                "ordering": ["-is_primary", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="website",
            constraint=models.UniqueConstraint(fields=["organization", "domain"], name="unique_org_domain"),
        ),
    ]

