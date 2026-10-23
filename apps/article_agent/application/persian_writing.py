"""Compact, reusable editorial guidance for Persian article prompts."""

from __future__ import annotations


def writing_standard(language: str, *, role: str) -> str:
    """Return only the guidance relevant to the current operation.

    Keeping this short and shared prevents a large repeated instruction block
    from consuming the bounded context budget at every provider call.
    """
    if not language.casefold().startswith("fa"):
        return (
            "Write directly for the stated audience. Add a distinct useful idea in each "
            "paragraph, avoid template openings and filler, and never strengthen or invent facts."
        )
    common = (
        "برای فارسی، متن را از ابتدا به فارسیِ روان و معیار بنویس: ترتیب طبیعی جمله‌ها، "
        "نشانه‌گذاری و نیم‌فاصلهٔ درست، واژگان متناسب با مخاطب و اصطلاحات یکدست. "
        "از لحن ترجمه‌ای، اداری و تبلیغاتی، کلی‌گویی، قطعیت بی‌پشتوانه و تکرار کلیدواژه پرهیز کن. "
        "هر بند باید نکته، دلیل، شرط، محدودیت یا نتیجهٔ عملیِ تازه‌ای داشته باشد؛ داده، مثال، منبع یا تجربه نساز."
    )
    role_rules = {
        "draft": (
            "با مقدمه‌های قالبی مانند «در دنیای امروز» یا «در این مقاله» شروع نکن؛ "
            "شروع را از مسئله یا نکتهٔ مشخص همین بخش انتخاب کن. گذار فقط وقتی بیاور که رابطهٔ منطقی دارد. "
            "نام شرکت، برند، سازمان، سامانه، مبلغ، مهلت، درصد، شرط حقوقی یا دستور اجرایی را فقط وقتی بنویس که در دادهٔ پژوهشِ داده‌شده پشتیبانی شده باشد؛ "
            "در غیر این صورت، راهنمایی را کلی، مشروط و قابل بررسی نگه دار."
        ),
        "continuation": (
            "از آخرین نکته ادامه بده، جمله‌ها یا تعریف‌های قطعهٔ قبل را تکرار یا بازگویی نکن و به سازوکار تولید اشاره نکن."
        ),
        "review": (
            "فقط ایرادهای عینی را گزارش کن: تکرار معنایی، مقدمهٔ کلیشه‌ای، عبارت ترجمه‌ای، گذارِ پرکننده، ادعای بی‌پشتوانه، "
            "یا کمبود توضیح مشخص. نثر فنی و دقیق را صرفاً به دلیل رسمی‌بودن ایراد نگیر."
        ),
        "revision": (
            "فقط ایرادهای مشخص را اصلاح کن؛ واقعیت، اصطلاح، احتیاط علمی و توضیح مفید را حفظ کن. متن را برای طولانی‌ترشدن بازنویسی نکن."
        ),
        "faq": (
            "سؤال را مانند پرسش واقعی خواننده بنویس، نه گونه‌ای از کلیدواژه؛ پاسخ را مستقیم، دقیق و بدون بازگویی بخش‌های مقاله بده."
        ),
        "conclusion": (
            "نتیجه را به تکرار تیترها یا مقدمه تبدیل نکن؛ مهم‌ترین معیار تصمیم، پیامد عملی یا محدودیت باقی‌مانده را بیان کن."
        ),
    }
    return f"{common} {role_rules.get(role, '')}".strip()
