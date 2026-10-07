from docx import Document
from django.test import SimpleTestCase

from apps.article_agent.infrastructure.document.docx_generator import DocxGenerator


class DocxGeneratorTests(SimpleTestCase):
    def test_generated_docx_contains_title_requested_headings_and_article_parts(self) -> None:
        article = {
            "title": "Article title",
            "sections": [{"heading": "First heading", "content": "First content"}, {"heading": "Second heading", "content": "Second content"}],
            "conclusion": "Conclusion", "FAQ": [{"question": "Question", "answer": "Answer"}],
            "common_mistakes": "Mistakes", "applications": "Applications",
        }
        output = DocxGenerator().generate(article)
        document = Document(output)
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        for expected in ("Article title", "First heading", "Second heading", "Conclusion", "Question", "Answer", "Mistakes", "Applications"):
            self.assertIn(expected, text)
