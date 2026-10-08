"""Deprecated legacy generator.

It is retained temporarily for historical compatibility only. Production jobs
run through ``ArticlePipeline`` and must not import this module.
"""

from copy import deepcopy

from apps.article_agent.infrastructure.ai.groq_client import GroqClient


class ArticleGenerator:
    MAX_CONTEXT_CHARS = 6000

    def __init__(self):
        self.llm = GroqClient()

    async def generate(self, article_data: dict) -> dict:
        article = deepcopy(article_data)

        target_words = int(article.get("word_count", 0))

        if target_words <= 0:
            raise ValueError("word_count must be greater than zero.")

        try:
            # =============================================
            # Sections
            # =============================================

            for index, section in enumerate(article.get("sections", [])):
                heading = section.get("heading", "").strip()

                if not heading:
                    continue

                generated_words = self._count_generated_words(article)
                remaining_words = max(
                    target_words - generated_words,
                    0,
                )

                recommended_words = self._calculate_recommended_words(
                    article=article,
                    remaining_words=remaining_words,
                )

                prompt = self._build_section_prompt(
                    article=article,
                    section_index=index,
                    heading=heading,
                    target_words=target_words,
                    generated_words=generated_words,
                    remaining_words=remaining_words,
                    recommended_words=recommended_words,
                )

                content = (await self.llm.generate(prompt)).strip()

                section["content"] = content

            # =============================================
            # Conclusion
            # =============================================

            generated_words = self._count_generated_words(article)
            remaining_words = max(
                target_words - generated_words,
                0,
            )

            recommended_words = self._calculate_recommended_words(
                article=article,
                remaining_words=remaining_words,
            )

            conclusion_prompt = self._build_conclusion_prompt(
                article=article,
                target_words=target_words,
                generated_words=generated_words,
                remaining_words=remaining_words,
                recommended_words=recommended_words,
            )

            article["conclusion"] = (await self.llm.generate(conclusion_prompt)).strip()

            # =============================================
            # FAQ Questions
            # =============================================

            generated_words = self._count_generated_words(article)
            remaining_words = max(
                target_words - generated_words,
                0,
            )

            recommended_words = self._calculate_recommended_words(
                article=article,
                remaining_words=remaining_words,
            )

            faq_questions_prompt = self._build_faq_questions_prompt(
                article=article,
                target_words=target_words,
                generated_words=generated_words,
                remaining_words=remaining_words,
                recommended_words=recommended_words,
            )

            faq_questions = (await self.llm.generate(faq_questions_prompt)).strip()

            questions = self._parse_questions(faq_questions)

            for index, faq_item in enumerate(article.get("FAQ", [])):
                if index < len(questions):
                    faq_item["question"] = questions[index]

            # =============================================
            # FAQ Answers
            # =============================================

            for faq_item in article.get("FAQ", []):
                question = faq_item.get("question", "").strip()

                if not question:
                    continue

                generated_words = self._count_generated_words(article)
                remaining_words = max(
                    target_words - generated_words,
                    0,
                )

                recommended_words = self._calculate_recommended_words(
                    article=article,
                    remaining_words=remaining_words,
                )

                answer_prompt = self._build_faq_answer_prompt(
                    article=article,
                    question=question,
                    target_words=target_words,
                    generated_words=generated_words,
                    remaining_words=remaining_words,
                    recommended_words=recommended_words,
                )

                faq_item["answer"] = (await self.llm.generate(answer_prompt)).strip()

            # =============================================
            # Common Mistakes
            # =============================================

            generated_words = self._count_generated_words(article)
            remaining_words = max(
                target_words - generated_words,
                0,
            )

            recommended_words = self._calculate_recommended_words(
                article=article,
                remaining_words=remaining_words,
            )

            mistakes_prompt = self._build_common_mistakes_prompt(
                article=article,
                target_words=target_words,
                generated_words=generated_words,
                remaining_words=remaining_words,
                recommended_words=recommended_words,
            )

            article["common_mistakes"] = (
                await self.llm.generate(mistakes_prompt)
            ).strip()

            # =============================================
            # Applications
            # =============================================

            generated_words = self._count_generated_words(article)
            remaining_words = max(
                target_words - generated_words,
                0,
            )

            recommended_words = self._calculate_recommended_words(
                article=article,
                remaining_words=remaining_words,
            )

            applications_prompt = self._build_applications_prompt(
                article=article,
                target_words=target_words,
                generated_words=generated_words,
                remaining_words=remaining_words,
                recommended_words=recommended_words,
            )

            article["applications"] = (
                await self.llm.generate(applications_prompt)
            ).strip()

            return article

        finally:
            await self.llm.close()

    # =====================================================
    # Word Count
    # =====================================================

    def _count_words(self, text: str) -> int:
        if not text:
            return 0

        return len(text.split())

    def _count_generated_words(self, article: dict) -> int:
        total = 0

        for section in article.get("sections", []):
            total += self._count_words(section.get("content", ""))

        total += self._count_words(article.get("conclusion", ""))

        for faq_item in article.get("FAQ", []):
            total += self._count_words(faq_item.get("question", ""))

            total += self._count_words(faq_item.get("answer", ""))

        total += self._count_words(article.get("common_mistakes", ""))

        total += self._count_words(article.get("applications", ""))

        return total

    def _count_remaining_tasks(self, article: dict) -> int:
        tasks = 0

        # Empty article sections
        for section in article.get("sections", []):
            heading = section.get("heading", "").strip()
            content = section.get("content", "").strip()

            if heading and not content:
                tasks += 1

        # Conclusion
        if not article.get("conclusion", "").strip():
            tasks += 1

        # FAQ question generation is one task
        faq = article.get("FAQ", [])

        if faq and not any(item.get("question", "").strip() for item in faq):
            tasks += 1

        # FAQ answers
        for item in faq:
            question = item.get("question", "").strip()
            answer = item.get("answer", "").strip()

            if question and not answer:
                tasks += 1

        # Common mistakes
        if not article.get("common_mistakes", "").strip():
            tasks += 1

        # Applications
        if not article.get("applications", "").strip():
            tasks += 1

        return max(tasks, 1)

    def _calculate_recommended_words(
        self,
        article: dict,
        remaining_words: int,
    ) -> int:
        if remaining_words <= 0:
            return 0

        remaining_tasks = self._count_remaining_tasks(article)

        recommended = remaining_words // remaining_tasks

        return min(
            remaining_words,
            max(recommended, 30),
        )

    # =====================================================
    # Context
    # =====================================================

    def _build_article_context(
        self,
        article: dict,
    ) -> str:
        parts = []

        title = article.get("title", "").strip()

        if title:
            parts.append(f"عنوان مقاله: {title}")

        headings = [
            section.get("heading", "").strip()
            for section in article.get("sections", [])
            if section.get("heading", "").strip()
        ]

        if headings:
            parts.append(
                "ساختار مقاله:\n" + "\n".join(f"- {heading}" for heading in headings)
            )

        completed_sections = []

        for section in article.get("sections", []):
            heading = section.get("heading", "").strip()
            content = section.get("content", "").strip()

            if heading and content:
                completed_sections.append(f"{heading}:\n{content}")

        if completed_sections:
            context = "\n\n".join(completed_sections)

            if len(context) > self.MAX_CONTEXT_CHARS:
                context = context[-self.MAX_CONTEXT_CHARS :]

            parts.append("بخش‌های قبلی تولیدشده:\n" + context)

        conclusion = article.get(
            "conclusion",
            "",
        ).strip()

        if conclusion:
            parts.append("نتیجه‌گیری فعلی:\n" + conclusion)

        return "\n\n".join(parts)

    # =====================================================
    # Prompt Metadata
    # =====================================================

    def _build_generation_metadata(
        self,
        target_words: int,
        generated_words: int,
        remaining_words: int,
        recommended_words: int,
    ) -> str:
        return f"""
اطلاعات مربوط به طول مقاله:

- تعداد کل کلمات هدف: {target_words}
- تعداد کلمات تولیدشده تا این لحظه: {generated_words}
- تعداد کلمات باقی‌مانده: {remaining_words}
- بودجه پیشنهادی برای این بخش: حدود {recommended_words} کلمه

این اعداد را در تولید متن رعایت کن.
متن تولیدشده نباید بدون دلیل بسیار بیشتر از بودجه پیشنهادی باشد.
اگر به انتهای بودجه رسیدی، متن را طبیعی و کامل جمع‌بندی کن.
""".strip()

    # =====================================================
    # Prompts
    # =====================================================

    def _build_section_prompt(
        self,
        article: dict,
        section_index: int,
        heading: str,
        target_words: int,
        generated_words: int,
        remaining_words: int,
        recommended_words: int,
    ) -> str:
        context = self._build_article_context(article)

        metadata = self._build_generation_metadata(
            target_words=target_words,
            generated_words=generated_words,
            remaining_words=remaining_words,
            recommended_words=recommended_words,
        )

        return f"""
شما یک نویسنده حرفه‌ای فارسی هستید.

{metadata}

{context}

وظیفه فعلی:
نوشتن محتوای بخش شماره {section_index + 1}

هدینگ فعلی:
{heading}

قوانین:
- فقط محتوای همین بخش را تولید کن.
- خود عنوان هدینگ را دوباره ننویس.
- مطالب بخش‌های قبلی را تکرار نکن.
- متن باید با بخش‌های قبلی از نظر معنا و لحن هماهنگ باشد.
- متن باید دقیق، طبیعی، روان و کاربردی باشد.
- از مقدمه‌چینی غیرضروری خودداری کن.
- از اطلاعات نامرتبط با موضوع مقاله استفاده نکن.
- خروجی فقط متن نهایی این بخش باشد.
- از Markdown اضافی، توضیح درباره فرایند تولید یا متن خارج از مقاله خودداری کن.
""".strip()

    def _build_conclusion_prompt(
        self,
        article: dict,
        target_words: int,
        generated_words: int,
        remaining_words: int,
        recommended_words: int,
    ) -> str:
        context = self._build_article_context(article)

        metadata = self._build_generation_metadata(
            target_words=target_words,
            generated_words=generated_words,
            remaining_words=remaining_words,
            recommended_words=recommended_words,
        )

        return f"""
شما یک نویسنده حرفه‌ای فارسی هستید.

{metadata}

{context}

وظیفه:
برای کل مقاله یک نتیجه‌گیری حرفه‌ای بنویس.

قوانین:
- نکات اصلی مقاله را جمع‌بندی کن.
- مطلب جدید و خارج از محتوای مقاله اضافه نکن.
- از تکرار جمله‌به‌جمله بخش‌های قبلی خودداری کن.
- نتیجه‌گیری باید طبیعی و مناسب پایان مقاله باشد.
- خروجی فقط متن نتیجه‌گیری باشد.
""".strip()

    def _build_faq_questions_prompt(
        self,
        article: dict,
        target_words: int,
        generated_words: int,
        remaining_words: int,
        recommended_words: int,
    ) -> str:
        context = self._build_article_context(article)

        metadata = self._build_generation_metadata(
            target_words=target_words,
            generated_words=generated_words,
            remaining_words=remaining_words,
            recommended_words=recommended_words,
        )

        return f"""
شما در حال تکمیل بخش FAQ یک مقاله فارسی هستید.

{metadata}

{context}

وظیفه:
دقیقاً 4 سوال متداول و مفید برای این مقاله تولید کن.

قوانین:
- سوال‌ها مستقیماً مرتبط با موضوع مقاله باشند.
- سوال‌ها تکراری نباشند.
- سوال‌ها از چیزهایی باشند که یک خواننده واقعی احتمالاً می‌پرسد.
- سوال‌ها کوتاه و واضح باشند.
- هر سوال در یک خط نوشته شود.
- شماره‌گذاری نکن.
- هیچ توضیح دیگری اضافه نکن.
""".strip()

    def _build_faq_answer_prompt(
        self,
        article: dict,
        question: str,
        target_words: int,
        generated_words: int,
        remaining_words: int,
        recommended_words: int,
    ) -> str:
        context = self._build_article_context(article)

        metadata = self._build_generation_metadata(
            target_words=target_words,
            generated_words=generated_words,
            remaining_words=remaining_words,
            recommended_words=recommended_words,
        )

        return f"""
شما یک نویسنده حرفه‌ای فارسی هستید.

{metadata}

{context}

سوال FAQ:
{question}

وظیفه:
به این سوال یک پاسخ دقیق، روشن و کاربردی بده.

قوانین:
- پاسخ مستقیماً به سوال مربوط باشد.
- با محتوای مقاله سازگار باشد.
- از تکرار غیرضروری مطالب خودداری کن.
- از اطلاعات نامرتبط استفاده نکن.
- پاسخ باید طبیعی و قابل فهم باشد.
- فقط پاسخ نهایی را برگردان.
""".strip()

    def _build_common_mistakes_prompt(
        self,
        article: dict,
        target_words: int,
        generated_words: int,
        remaining_words: int,
        recommended_words: int,
    ) -> str:
        context = self._build_article_context(article)

        metadata = self._build_generation_metadata(
            target_words=target_words,
            generated_words=generated_words,
            remaining_words=remaining_words,
            recommended_words=recommended_words,
        )

        return f"""
شما یک نویسنده حرفه‌ای فارسی هستید.

{metadata}

{context}

وظیفه:
بخش «اشتباهات رایج» این مقاله را بنویس.

قوانین:
- اشتباهات واقعاً مرتبط با موضوع مقاله را توضیح بده.
- هر مورد را کوتاه ولی کاربردی توضیح بده.
- مطالب تکراری با بخش‌های قبلی تولید نکن.
- متن باید برای خواننده مفید باشد.
- فقط محتوای این بخش را برگردان.
""".strip()

    def _build_applications_prompt(
        self,
        article: dict,
        target_words: int,
        generated_words: int,
        remaining_words: int,
        recommended_words: int,
    ) -> str:
        context = self._build_article_context(article)

        metadata = self._build_generation_metadata(
            target_words=target_words,
            generated_words=generated_words,
            remaining_words=remaining_words,
            recommended_words=recommended_words,
        )

        return f"""
شما یک نویسنده حرفه‌ای فارسی هستید.

{metadata}

{context}

وظیفه:
بخش «کاربردها» این مقاله را بنویس.

قوانین:
- کاربردهای واقعی و مهم موضوع را توضیح بده.
- کاربردها باید با موضوع و محتوای مقاله هماهنگ باشند.
- از مطالب تکراری و بی‌ارتباط خودداری کن.
- متن باید کاربردی و قابل فهم باشد.
- فقط محتوای این بخش را برگردان.
""".strip()

    # =====================================================
    # Helpers
    # =====================================================

    def _parse_questions(self, text: str) -> list[str]:
        questions = []

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            if line[0].isdigit():
                line = line.lstrip("0123456789")
                line = line.lstrip(".-:) ")

            if line:
                questions.append(line)

        return questions[:4]
