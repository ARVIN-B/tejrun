# برنامهٔ اجرایی: برند، متادیتای سئو و بازبینی تخصصی مقاله

## وضعیت اجرا — ۲۰ اکتبر ۲۰۲۶

- اجرا شد: فیلد اختیاری و migration افزایشی برند، انتقال آن از فرم تا `ArticleRequest` و context نویسنده، و policy جلوگیری از ادعای تجاریِ ساختگی.
- اجرا شد: تولید متای ساخت‌یافته با fallback deterministic، ذخیره در `result_payload`، و نمایش متا/برند/تعداد نظرها در dashboard.
- اجرا شد: coordinator ترتیبی و context-bounded برای نقش‌های SEO، ویراستار فارسی، مقاله‌نویس، برق صنعتی و سامانه خورشیدی؛ output نامعتبر provider به diagnostic امن تبدیل می‌شود.
- اجرا شد: نگه‌داری نظرهای بخش در `ArticleSection.review_payload` و نظرهای مقاله در نتیجهٔ نهایی.
- تصمیم اجرایی جدید: word budget یک کنترل best-effort است. تلاش محدود برای رسیدن به بازه حفظ شده، ولی طول خارج از بازه فقط warning تشخیصی می‌دهد و job را متوقف نمی‌کند.

## هدف و مرز این سند

این سند برنامهٔ مرحله‌ای پیاده‌سازی سه قابلیت در `apps/article_agent` است:

1. دریافت و استفادهٔ کنترل‌شده از نام برند در مقاله.
2. تولید و نمایش `meta title` و `meta description` برای هر خروجی.
3. دریافت نظر ساخت‌یافته از پنج پرسونای تخصصی در هر چرخهٔ نگارش/بازبینی: متخصص سئو، ویراستار فارسی، مقاله‌نویس، متخصص برق صنعتی و متخصص پنل خورشیدی.

این مرحله عمداً فقط برنامه است؛ هیچ تغییر رفتاری، migration یا prompt اجرایی در این مرحله انجام نمی‌شود. پیاده‌سازی باید افزایشی باشد و مسیر تولید فعلی را بازنویسی نکند.

## یافته‌های مسیر فعلی

مسیر واقعی تولید اکنون چنین است:

`create_article.html` → `create_article_job` → `Article` و `ArticleJob` → `generate_article_task(job_id)` → `ArticleJobExecutionService` → `ArticlePipeline` → ذخیرهٔ بخش‌ها/خروجی DOCX.

منبع معتبر درخواست `Article` است و نسخهٔ قابل بازیابی آن در `ArticleJob.request_payload` نگه‌داری می‌شود. `ArticleRequest` قرارداد مستقل دامنه است. پیش‌نویس و بازبینی هر بخش در `ArticleSection` ذخیره می‌شود و بازبینی مقاله در `ArticlePipeline` پس از تکمیل بخش‌ها انجام می‌گیرد. بنابراین فقط افزودن چند فیلد HTML کافی نیست: داده باید از فرم تا قرارداد دامنه، checkpoint، retry، نتیجهٔ API و DOCX (در صورت انتخاب محصول) مسیر کامل و آزموده داشته باشد.

## اصول غیرقابل‌مذاکره

- متن کامل و رو به رشد مقاله به هیچ یک از پنج متخصص ارسال نمی‌شود. هر فراخوانی فقط context فشرده و بودجه‌بندی‌شده دریافت می‌کند: طرح، حافظهٔ فشرده، تحقیقِ قابل استناد، بخش هدف یا excerptهای محدود مقاله.
- مدل تنها «نظر محدود و ساخت‌یافته/متنی» می‌دهد؛ اعتبارسنجی، شدت، انتخاب بخش‌های متاثر، ادغام نظرها، تصمیم اصلاح، بودجهٔ کلمه و persistence در کد برنامه باقی می‌ماند.
- نام برند اختیاری است. نبود آن باید کاملاً backward-compatible باشد و هیچ متن «برند ناشناس» یا جای‌خالی در مقاله ایجاد نکند.
- برند نباید باعث ادعای تجاری، فنی یا پزشکی/ایمنیِ اثبات‌نشده، keyword stuffing، یا تکرار مصنوعی شود. استفاده از آن باید طبیعی و فقط در جای مفید به خواننده باشد.
- متادیتا جزء بدنه و بودجهٔ کلمات مقاله نیست. باید جداگانه اعتبارسنجی، ذخیره و نمایش داده شود.
- نقش‌های «متخصص» پرسونای بازبینی LLM هستند، نه تأیید انسان یا مشاورهٔ مهندسی دارای مجوز. برای نکات ایمنی یا ادعاهای فنیِ پرخطر، خروجی باید به یافتهٔ قابل‌پیگیری/منبع تحقیق گره بخورد یا به‌صورت هشدار برای بررسی انسانی ثبت شود.
- در خطای provider، لغو، retry، crash worker یا خروجی خراب، checkpoint فقط دادهٔ معتبر را بازیابی می‌کند و گزارش‌های ناقص را به جای نتیجهٔ معتبر نمایش نمی‌دهد.

## قرارداد محصول پیشنهادی

### 1. نام برند

- فیلد `brand_name` روی `Article`: `CharField(max_length=160, blank=True, default="")`.
- همان مقدار نرمال‌شده در `ArticleJob.request_payload` ثبت می‌شود تا job قابل audit و retry باشد؛ `Article` همچنان مرجع اصلی درخواست است.
- `ArticleRequest` دارای `brand_name: str = ""` می‌شود. serialization و deserialization با default خالی برای payloadهای قدیمی سازگار می‌مانند.
- اعتبارسنجی ورودی: trim، حذف فضای زائد، حداکثر 160 نویسه؛ مقدار خالی مجاز است. خطای API باید نام فیلد و علت دقیق را برگرداند.
- policy استفاده: طرح مقاله فقط constraint کوتاه برند را می‌بیند؛ نویسنده فقط در مقدمه/جمع‌بندی/نمونه‌ای که واقعاً مرتبط است از آن استفاده می‌کند؛ حداکثر دفعات استفاده با شمارش deterministic کنترل می‌شود. نام برند هرگز جای منبع، عدد، استاندارد یا نام محصول تأییدنشده را نمی‌گیرد.

### 2. متا تایتل و متا دیسکریپشن

متادیتا یک شیء نسخه‌پذیر در `result_payload["article"]["seo_metadata"]` خواهد بود:

```json
{
  "meta_title": "...",
  "meta_description": "...",
  "source": "generated",
  "validation": {"title_length": 0, "description_length": 0}
}
```

- برای دسترسی سریع و نمایش dashboard، در همان milestone بررسی می‌شود که آیا دو ستون denormalized روی `Article` لازم است یا نتیجهٔ JSON کفایت می‌کند. پیشنهاد اولیه: تا زمانی که جست‌وجو/فیلتر SQL لازم نیست، منبع حقیقت `result_payload` باشد تا migration بی‌دلیل نداشته باشیم؛ `brand_name` به‌دلیل ورودی اصلی بودن ستون مستقل است.
- یک `MetadataWriter`/`SeoMetadataService` جدا از نویسندهٔ بدنه ایجاد می‌شود. این سرویس فقط عنوان، کلمات کلیدی، برند، intent، plan، یافته‌های SEO و خلاصه/ excerptهای محدودِ مقاله را می‌گیرد؛ هرگز کل متن بلند مقاله را دریافت نمی‌کند.
- خروجی مدل با schema سخت‌گیرانه parse می‌شود. پس از normalize باید غیرخالی، بدون markdown/HTML ناخواسته، بدون keyword stuffing و در سقف پیکربندی‌شده باشد. مقادیر پیشنهادی اولیه: meta title حداکثر 60 نویسه و meta description حداکثر 160 نویسه؛ حداقل‌ها باید پس از تأیید محصول تعریف شوند تا متن فارسی طبیعی قربانی محدودیت خشک نشود.
- اگر خروجی malformed یا خارج از سقف بود: یک repair محدود با همان context؛ اگر باز هم نامعتبر بود، fallback deterministic از عنوان/کلیدواژه با ثبت warning ساخته می‌شود. شکست متادیتا نباید مقالهٔ صحیح را از چاپ متوقف کند، اما وضعیت fallback در نتیجه و log روشن خواهد بود.
- در صفحهٔ نتیجه/جزئیات job، کارت «اطلاعات سئو» با دکمهٔ کپی برای هر دو فیلد نشان داده می‌شود. در DOCX به‌صورت پیش‌فرض بخش قابل رؤیت بدنه اضافه نمی‌شود؛ متا برای انتشار وب است. اگر محصول واقعاً آن را در فایل می‌خواهد، به شکل appendix برچسب‌دار و خارج از بودجهٔ کلمات اضافه می‌شود. این تصمیم پیش از implementation نهایی می‌شود.

### 3. نظرهای تخصصی

قرارداد داخلی پیشنهادی برای هر نظر:

```json
{
  "role": "seo|persian_editor|article_writer|industrial_electrical|solar",
  "scope": "section|article",
  "applicable": true,
  "score": 0.0,
  "findings": [
    {
      "type": "...",
      "severity": "low|medium|high|critical",
      "affected_units": ["section:0"],
      "evidence": "excerpt کوتاه از متن ارسالی",
      "recommendation": "دستور اصلاح مشخص و قابل اجرا"
    }
  ],
  "strengths": [],
  "required_fixes": []
}
```

- `SpecialistOpinion` و serializer آن به domain اضافه می‌شود. ورودی/خروجی نامعتبر provider به `ContractValidationError` با نام role، scope و بخش خراب تبدیل می‌شود و متن تشخیصی provider با redaction کلید/اطلاعات حساس در log ثبت می‌گردد.
- همهٔ roleها در هر scope فراخوانی می‌شوند، اما roleهای فنی مجازند با `applicable=false` و دلیل کوتاه برگردند وقتی موضوع واقعاً خارج از حوزه است. این کار «سکوت ساختگی» را از «نظر ندارم» جدا می‌کند.
- یک `SpecialistReviewCoordinator` نقش‌ها را به ترتیب کنترل‌شده اجرا می‌کند، خروجی‌ها را validate، deduplicate و به `ReviewResult`/`ArticleReview` موجود تبدیل می‌کند. ترتیب پیش‌فرض sequential است تا فشار TPD/RPM و زمان task قابل پیش‌بینی بماند؛ بعد از سنجش واقعی می‌توان concurrency محدود و rate-limit-aware اضافه کرد.
- فقط یافته‌های high/critical یا required fix معتبر به revision راه می‌یابند. یافته‌های مشابه از roleهای مختلف ادغام می‌شوند، اما provenance نقش‌ها در payload باقی می‌ماند. اصلاح همیشه targetted است و نباید بخش‌های بی‌ربط را بازنویسی کند.
- opinions بخش در `ArticleSection.review_payload["specialist_opinions"]` ذخیره می‌شود؛ opinions مقاله و نتایج aggregation در checkpoint/result payload قرار می‌گیرد. checkpoint باید version و scope را داشته باشد تا retry، نظرهای یک draft قدیمی را با draft جدید اشتباه نگیرد.

## طراحی promptهای تخصصی

فایل جدید پیشنهادی: `apps/article_agent/application/specialist_review_prompts.py`. هر prompt از یک shell مشترک کوتاه و role instruction اختصاصی تشکیل می‌شود. از تکرار متن طولانی پرهیز می‌شود؛ context از `ContextBuilder` آمده و سقف جداگانه دارد.

### shell مشترک برای هر پنج نقش

```text
تو یک بازبین مشورتی هستی، نه نویسندهٔ جایگزین و نه منبع حقیقت.
فقط متن و داده‌های داخل CONTEXT را ارزیابی کن. حقیقت، عدد، استاندارد، نام برند یا ادعای بیرونی نساز.
اگر موضوع در حوزهٔ نقش تو نیست، applicable=false و دلیل کوتاه بده.
فقط موارد مشخص و قابل اقدام را گزارش کن؛ از توصیه‌های کلی، لحن تبلیغاتی و بازنویسی کامل پرهیز کن.
برای هر finding، واحد متاثر، یک شاهد کوتاه از متن موجود، شدت و دستور اصلاح مشخص بده.
خروجی فقط JSON مطابق schema است؛ حداکثر N finding.
```

`N` برای بخش 5 و برای مقاله 8 است؛ سقف output token و سقف نویسهٔ evidence نیز در کد enforce می‌شود.

### متخصص سئو (`seo`)

```text
نقش: استراتژیست SEO فارسی با تمرکز بر intent، ساختار محتوا و اسنیپت.
بررسی کن: هم‌خوانی عنوان/headingها با intent؛ پوشش طبیعی کلیدواژه و مترادف‌ها؛ یکتایی هدف هر heading؛ پیوند منطقی بخش‌ها؛ خوانایی برای جست‌وجو؛ خطر keyword stuffing؛ و سازگاری meta title/meta description با موضوع و برند.
بررسی نکن: وعدهٔ رتبه، حجم جست‌وجو یا آمار بیرونی بدون دادهٔ معتبر.
در پیشنهادها، محل دقیق تغییر و علت آن برای کاربر جست‌وجو را بنویس؛ تکرار نام برند را پیشنهاد نده مگر به روشن شدن مالکیت محتوا کمک کند.
```

### ویراستار فارسی (`persian_editor`)

```text
نقش: ویراستار حرفه‌ای فارسی برای متن آموزشی/فنیِ روان.
بررسی کن: سلامت املا، نیم‌فاصله و نشانه‌گذاری؛ جمله‌های ترجمه‌زده یا AI-گونه؛ ابهام مرجع ضمیر؛ تکرار واژه/ساختار؛ پیوستگی پاراگراف‌ها؛ تناسب لحن با مخاطب؛ و طبیعی بودن کاربرد نام برند.
اصل: متن را بی‌دلیل رسمی، کلیشه‌ای یا تبلیغاتی نکن. فقط اشکال‌های دارای شاهد را ثبت کن و برای هرکدام جایگزین/دستور کوتاه پیشنهاد بده.
```

### مقاله‌نویس (`article_writer`)

```text
نقش: مقاله‌نویس فارسیِ باتجربه در محتوای آموزشیِ تصمیم‌یار.
بررسی کن: آیا هر بخش وعدهٔ heading را محقق می‌کند؛ آغاز و پایان طبیعی‌اند؛ توضیح، مثال و نتیجه به ترتیب قابل فهم آمده‌اند؛ گذارها و مسیر خواننده روشن است؛ متن به اندازهٔ کافی مشخص و مفید است؛ و نتیجه‌گیری صرفاً تکرار نیست.
از اضافه‌کردن واقعیت، مثال واقعی یا تجربهٔ ادعایی که در context نیست خودداری کن. اگر متن به اصلاح نیاز ندارد، finding نساز.
```

### متخصص برق صنعتی (`industrial_electrical`)

```text
نقش: بازبین فنی برق صنعتی با اولویت ایمنی و دقت اصطلاحات.
بررسی کن: اطلاق درست اصطلاحات، روابط علت‌ومعلولی، مرز کاربرد تجهیزات، هشدارهای ایمنی، ادعاهای راندمان/ظرفیت/استاندارد و دستورهای عملیاتی.
هر ادعای فنیِ تأییدنشده، دستور خطرناک یا تعمیم نادرست را high/critical کن و بگو برای اصلاح به منبع معتبر یا بررسی مهندس دارای صلاحیت نیاز دارد. استاندارد، عدد، ظرفیت یا راهکار اجرایی از خودت نساز.
اگر موضوع برق صنعتی نیست، صریحاً applicable=false بده.
```

### متخصص پنل خورشیدی (`solar`)

```text
نقش: بازبین فنی سامانه‌های فتوولتائیک با اولویت ایمنی، کارکرد واقعی و پرهیز از وعده‌های اغراق‌آمیز.
بررسی کن: درستی تمایز پنل/اینورتر/باتری/سازه/حفاظت؛ وابستگی تولید به تابش، دما، سایه، جهت و طراحی؛ ادعاهای صرفه‌جویی/تولید؛ محدودیت نصب و نگه‌داری؛ و هشدارهای ایمنی الکتریکی.
ادعای عددی، استاندارد یا راهنمای نصب را بدون research معتبر تأیید نکن. یافتهٔ پرخطر را high/critical و قابل ارجاع به بررسی انسانی بنویس. اگر موضوع فتوولتائیک نیست، applicable=false بده.
```

## نقشهٔ تغییرات فایل‌ها

| ناحیه | فایل‌های اصلی | تغییر برنامه‌ریزی‌شده |
| --- | --- | --- |
| مدل/دیتابیس | `models.py`, migration جدید | افزودن `Article.brand_name` با default امن؛ migration additive و قابل rollback منطقی |
| فرم و API | `presentation/web/views.py`, `templates/article_agent/create_article.html` | فیلد برند، validation دقیق، ارسال payload، نمایش برند؛ endpoint status شامل brand و metadata بعد از completion |
| قراردادها | `domain/contracts.py`, `domain/serialization.py` | `brand_name` در `ArticleRequest`؛ قرارداد/serializer نظر تخصصی و SEO metadata با compatibility payloadهای قدیمی |
| اجرا و persistence | `application/job_execution.py` | انتقال brand به request؛ wiring سرویس metadata و coordinator؛ ذخیرهٔ نتیجه/checkpoint بدون تغییر قرارداد Celery (`job_id` تنها) |
| pipeline | `application/article_pipeline.py` | stageهای محدود برای specialist review و metadata، checkpoint versioned، تجمیع یافته‌ها و revision هدفمند |
| سرویس‌های LLM | `application/services.py` و فایل‌های جدید | سرویس metadata، coordinator، promptهای مرکزی، parse/diagnostic/error handling؛ استفاده از `ContextBuilder` در همهٔ callها |
| رندر | `infrastructure/document/docx_generator.py` | فقط اگر تصمیم محصول append metadata را تأیید کند؛ در غیر این صورت عدم تغییر بدنه DOCX |
| تنظیمات | `config/settings.py`, `.env.example` | سقف context/output/retry، roleهای enabled، سقف findings و طول meta با defaultهای امن |
| آزمون/مستندات | `apps/article_agent/tests/`, runbook/checklist | آزمون هر قرارداد، migration، مسیر job، retry/checkpoint، context limit، و UI/API |

## مراحل پیاده‌سازی و نقاط توقف

### Milestone A — baseline و تصمیم‌های محصول

1. اجرای آزمون‌های هدفمند و ثبت baseline پیش از تغییر؛ مشکلات از قبل موجود جدا از regressionهای جدید می‌مانند.
2. تثبیت دو تصمیم: نمایش متا فقط در dashboard/result یا appendix DOCX؛ و سقف نهایی نویسه‌های meta پس از نمونه‌سازی فارسی.
3. ثبت budget فراخوانی‌ها: پنج review بخش + پنج review مقاله در بدترین حالت، تعداد revisionها، token reservation و timeout Celery. اگر این بودجه از ظرفیت provider بیشتر است، اجرا نباید «بی‌نهایت» retry شود؛ باید checkpoint، retry با تشخیص واضح و ادامه از key/provider مجاز داشته باشد.

**خروجی پذیرش:** baseline مستند، تصمیم‌های محصول ثبت‌شده و هیچ تغییر production هنوز اعمال نشده است.

### Milestone B — برند end-to-end

1. افزودن migration و مدل؛ اجرای migration روی دیتابیس آزمایشی و بررسی داده‌های قدیمی با brand خالی.
2. افزودن فیلد دسترس‌پذیر فارسی به modal، محدودیت client-side فقط برای UX و validation server-side به‌عنوان مرجع.
3. توسعهٔ request/serializer/job payload/execution service.
4. افزودن constraint مختصر برند به planning/writing context بدون افزایش context خارج از budget.
5. آزمون ساخت job، retry و job قدیمی فاقد brand.

**خروجی پذیرش:** برند اختیاری از UI تا یک context نویسنده حرکت می‌کند؛ job قدیمی و brand خالی شکست نمی‌خورند؛ استفادهٔ برند با policy قابل آزمون است.

### Milestone C — متادیتای مقاوم

1. تعریف contract و validator metadata؛ نوشتن تست‌های malformed JSON، متن خالی، طول خارج از محدوده، HTML/markdown و fallback.
2. افزودن سرویس تولید metadata پس از آن‌که نسخهٔ نهایی مقاله تثبیت شد و قبل از persist result/render (بسته به تصمیم DOCX).
3. ارسال context فشرده و واقعی؛ عدم ارسال کل مقاله. خروجی repair یک‌باره و fallback deterministic.
4. افزودن metadata به result payload و endpoint status/جزئیات؛ طراحی کارت نمایش و کپی در UI.
5. افزدن metadata به DOCX فقط اگر تصمیم Milestone A آن را خواسته باشد.

**خروجی پذیرش:** هر job completed متای معتبر یا fallback علامت‌دار دارد؛ شکست metadata مقالهٔ قابل‌چاپ را از بین نمی‌برد؛ بدنه/word budget تغییر نکرده است.

### Milestone D — زیرساخت نظرهای پنج‌گانه

1. اضافه کردن enum/contract/serializer و promptهای مرکزی؛ هر prompt تحت آزمون snapshot یا assertion برای role، schema، محدودیت امنیتی و عدم وعدهٔ بیرونی.
2. پیاده‌سازی `SpecialistReviewCoordinator` روی interface فعلی `TextGenerator`، با operation نام‌دار برای diagnostics/rate-limit و context اختصاصی محدود.
3. parse و validation سخت‌گیرانه، redacted diagnostics، dedupe و merge deterministic؛ provider output هرگز مستقیم تصمیم persistence یا edit را کنترل نمی‌کند.
4. ذخیرهٔ opinionهای valid با `draft_revision`/`scope`/`role` در review payload/checkpoint، به‌گونه‌ای که resume تنها همان draft را بازیابی کند.
5. تست cancellation بین roleها، خطای یک role، خروجی ناقص، تکرار retry و عدم رشد نامحدود checkpoint.

**خروجی پذیرش:** هر پنج role در scopeهای section و article فراخوانی قابل مشاهده دارند، context سقف دارد و خروجی خراب provider به خطای قابل تشخیص/رفتار تعریف‌شده تبدیل می‌شود.

### Milestone E — اتصال به چرخهٔ review و اصلاح هدفمند

1. پس از هر draft بخش، review عمومی فعلی و پنج opinion نقش‌دار به یک `ReviewResult` قابل‌ردیابی aggregate می‌شوند؛ سپس فقط اصلاح‌های لازم انجام می‌شود.
2. پس از review مقاله، پنج opinion با excerptهای مقاله به `ArticleReview` aggregate می‌شوند. `FinalEditor` فقط واحدهای متاثر را می‌گیرد.
3. پس از هر targeted edit، فقط بخش‌های تغییر کرده دوباره با coordinator بررسی می‌شوند؛ بخش‌های سالم بازنویسی نمی‌شوند.
4. stage/progressهای واضح به dashboard اضافه می‌شود، مانند «بازبینی تخصصی بخش ۲ از ۵»؛ transitionهای `JobStatus` و cancellation حفظ می‌شوند.
5. نتیجهٔ نقش‌ها به کاربر در view جزئیات/نتیجه با severity و توصیه نمایش داده می‌شود، نه raw prompt یا secrets.

**خروجی پذیرش:** اصلاح‌ها provenance دارند، loop بی‌نهایت نمی‌شود (سقف revision ثابت)، و بخش غیرمتاثر تغییر نمی‌کند.

### Milestone F — hardening و تحویل

1. آزمون migration، unit، integration pipeline، persistence، endpoint و renderer؛ سپس اجرای suite گسترده‌تر.
2. تست حجم مقالهٔ بلند و roleهای پنج‌گانه با fake generator که اندازهٔ context و تعداد فراخوانی را ثبت می‌کند.
3. تست retry/cancel/crash-resume و rotation/rate-limit provider با checkpoint معتبر؛ تشخیص error باید role، operation، مدل، retry-after و پیام redacted provider را نگه دارد.
4. بررسی diff، migration plan، تنظیمات example و به‌روزرسانی `IMPLEMENTATION_RUNBOOK.md` و `ACCEPTANCE_CHECKLIST.md` با شواهد واقعی.

## ماتریس آزمون حداقلی

- UI/API: brand خالی، brand فارسی/لاتین، brand بیش از سقف، whitespace، job status و retry.
- Compatibility: request payload قدیمی بدون brand/metadata/opinions؛ job در حال اجرا با checkpoint نسخهٔ قدیمی.
- Metadata: JSON صحیح، invalid/missing field، خروجی بیش از سقف، repair موفق/ناموفق، fallback، عدم تغییر word accounting.
- Prompt/coordinator: دقیقاً پنج role، operation نام‌دار، context محدود، `applicable=false`، severity نامعتبر، affected unit نامعتبر، dedupe و provenance.
- Pipeline: draft → پنج نظر → revision هدفمند → re-review؛ article review → targeted edit → review مجدد فقط برای واحدهای تغییرکرده.
- Resilience: cancellation میان roleها، provider 429/TPD، provider empty/malformed، timeout، worker resume، persist failure و DOCX failure.
- Safety/quality: ادعای فنی تأییدنشده، دستور نصب/برق پرخطر، keyword stuffing، استفادهٔ مصنوعی برند و فارسی غیرطبیعی.

## ریسک‌ها و کنترل‌ها

| ریسک | کنترل |
| --- | --- |
| پنج role زمان و مصرف provider را چندبرابر می‌کنند | context/output کوچک، execution ترتیبی، quota-aware retry، checkpoint، telemetry برای تعداد call/token/duration هر role |
| پر شدن context برای مقالهٔ بلند | استفادهٔ اجباری از `ContextBuilder` و excerpt budget؛ تست اندازهٔ prompt؛ عدم ارسال متن کامل |
| loop اصلاح و افزایش زمان Celery | حداکثر revision per section/article، dedupe findings، و توقف با error تشخیصی یا warning تعریف‌شده |
| hallucination فنی یا خطر ایمنی | roleهای فنی فقط یافته می‌دهند، source/provenance اجباری برای ادعای حساس، escalation به بررسی انسانی |
| ناسازگاری jobهای قدیمی | defaults در contract/serializer، migration additive، checkpoint schema version |
| نشت داده یا کلید API در diagnostics | redaction مرکزی، عدم persist prompt خام یا headers حساس، نمایش خلاصهٔ امن در UI |

## معیار نهایی پذیرش

کار تمام‌شده فقط وقتی اعلام می‌شود که شواهد آزمونی نشان دهد:

1. کاربر می‌تواند نام برند اختیاری وارد کند و آن به‌صورت طبیعی و کنترل‌شده در خروجی به کار می‌رود.
2. هر مقالهٔ کامل، meta title و meta description معتبر یا fallback مشخص دارد و این داده‌ها در dashboard/result قابل مشاهده‌اند.
3. در هر چرخهٔ تعریف‌شدهٔ draft/review، هر پنج پرسونای تخصصی نظر ساخت‌یافتهٔ قابل‌ردیابی می‌دهند؛ نظر غیرمرتبط صریحاً `not applicable` است.
4. متن کامل مقاله به roleها ارسال نمی‌شود و آزمون اندازهٔ context این موضوع را اثبات می‌کند.
5. اصلاح‌ها هدفمندند، word budget و FAQ چهارگانه حفظ می‌شوند، و retry/cancel/checkpoint/render مسیر واقعی را نمی‌شکنند.
6. migration، suiteهای هدفمند و suite گستردهٔ مرتبط پاس شده‌اند؛ هر failure قبلی یا بیرونی با علت و شواهد جداگانه گزارش شده است.
