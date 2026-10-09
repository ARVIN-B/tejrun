from pathlib import Path

from django.test import SimpleTestCase


class EnvironmentTemplateTests(SimpleTestCase):
    def test_environment_template_contains_no_usable_credentials(self) -> None:
        template = Path(__file__).resolve().parents[3] / ".env.example"
        values = {}
        for line in template.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key] = value

        for key in (
            "AUTOGEN_API_KEY",
            "LLM_API_KEY",
            "TELEGRAM_BOT_TOKEN",
            "DB_PASSWORD",
            "ARTICLE_AGENT_RESEARCH_API_KEY",
            "EMAIL_HOST_PASSWORD",
        ):
            self.assertEqual(values[key], "", f"{key} must not contain a usable credential")
        self.assertEqual(
            values["DJANGO_SECRET_KEY"],
            "replace-with-a-long-random-django-secret",
        )
