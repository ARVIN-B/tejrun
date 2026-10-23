# گزارش ممیزی فنی پروژه — ۲۱ اکتبر ۲۰۲۶

## دامنه و روش

این گزارش یک ممیزی ایستا و رفتاریِ فقط‌خواندنی از کل مخزن است؛ تمرکز اصلی بر
`apps/article_agent` بوده، اما مسیرهای قابل اجرا، تنظیمات، داشبورد و سامانهٔ
چت نیز بررسی شده‌اند. هیچ تغییری برای رفع ایرادها در این مرحله اعمال نشده است.

معیار اولویت:

- **P0:** نقص امنیتی یا مسیر اجراییِ قطعاً خراب که باید پیش از انتشار رفع شود.
- **P1:** خطر جدی در صحت خروجی، دوام job یا عملیات production.
- **P2:** نقص مهم کیفیت، قابلیت نگهداری یا تجربهٔ کاربر.
- **P3:** کد مرده، بدهی فنی یا بهبود کم‌خطر.

## نتیجهٔ اجرایی

انتشار production در وضعیت فعلی توصیه نمی‌شود. چهار مانع P0 عبارت‌اند از:

1. endpoint عمومی چت هم بدون کنترل دسترسی، هزینهٔ LLM ایجاد می‌کند و هم به علت
   فراخوانی اشتباه، قطعاً با `TypeError` پاسخ 500 می‌دهد.
2. فایل zip رهگیری‌شده در Git شامل `.env` است؛ حتی بدون بازکردن محتوای آن، این
   یک مسیر بالقوه برای نشت credential است.
3. دو migration لازم Article Agent در دیتابیس بررسی‌شده اعمال نشده‌اند.
4. گیت‌های کیفیتی که طبق مشخصات باید مانع completion شوند، عملاً هشدار هستند و
   مقاله با review یا quality report ناموفق چاپ و ذخیره می‌شود.

همچنین شرط قبلی محصول مبنی بر «چاپ شدن مقاله حتی با امتیاز کم یا اختلاف تعداد
کلمات» با مشخصات سخت‌گیرانهٔ فعلی تعارض دارد. این سیاست می‌تواند درست باشد، اما
باید صریحاً به یک قرارداد محصولی تبدیل شود: خروجی قابل‌انتشار نیست مگر با وضعیت
کیفیِ آشکار و قابل پیگیری؛ در غیر این صورت داشبورد موفقیت را گزارش می‌کند در
حالی که متن ممکن است معیارهای حیاتی را رد کرده باشد.

## یافته‌های P0

### P0-01 — endpoint چت عمومی، هزینه‌زا و در عمل خراب است

**کامنت ممیزی:** `ChatView` یک `AutoGenChatbot` می‌سازد، ولی `ChatUseCase` را با
یک آرگومان فراخوانی می‌کند؛ سازنده دو آرگومان لازم دارد. حتی در صورت اصلاح آن،
فراخوانی `execute(message)` نیز ترتیب و تعداد آرگومان‌های لازم (`source`,
`external_id`, `message`) را ندارد. بنابراین نخستین درخواست معتبر API با 500
تمام می‌شود. از طرف دیگر `APIView` هیچ permission یا throttle ندارد و تنظیمات
REST Framework نیز permission سراسری تعیین نکرده‌اند؛ پس در Django REST Framework
به‌صورت پیش‌فرض endpoint عمومی است و پس از رفع TypeError می‌تواند بدون محدودیت
هزینهٔ LLM بسازد.

**شواهد:**
`apps/social_media_chatbot/presentation/api/views.py:18-38`،
`apps/social_media_chatbot/application/use_cases/chat.py:6-57`،
`config/settings.py:62-64`.

**اثر:** قطع کامل API چت، سپس خطر سوءاستفاده/هزینه و ذخیرهٔ مکالمات ناشناس.

**پیشنهاد رفع:** یک قرارداد request روشن بسازید (شناسهٔ کانال/کاربر و شناسهٔ bot
نباید از body دلخواه و بدون احراز هویت پذیرفته شود)، repository را تزریق کنید،
`ChatUseCase` را با keyword argument فراخوانی کنید، و permission، rate limit و
quota را در سطح endpoint و provider اعمال کنید. برای endpoint عمومی، امضای HMAC
یا token مخصوص integration لازم است.

**تأیید پس از رفع:** تست integration برای 401/403، درخواست معتبر، شناسهٔ کاربر
معتبر، محدودیت نرخ و بسته‌شدن client در خطای provider.

### P0-02 — آرشیو رهگیری‌شده شامل `.env` است

**کامنت ممیزی:** فایل `energy project.zip` در Git رهگیری شده و فهرست داخلی آن
ورودی `.env` را نشان می‌دهد. محتوای آرشیو خوانده یا افشا نشد، اما وجود `.env` در
یک artifact قابل commit برای secret exposure کافی است.

**شواهد:** `energy project.zip`، در کنار `.gitignore:20-25` که فقط فایل env در
working tree را نادیده می‌گیرد و archive را حذف نمی‌کند.

**اثر:** احتمال افشای کلیدهای LLM، رمز DB، Telegram token و تنظیمات production
در cloneها، backupها و تاریخچهٔ Git.

**پیشنهاد رفع:** archive را با یک commit مجزا از Git حذف کنید، با ابزارهایی مانند
`git filter-repo` یا BFG آن را از تاریخچه پاک کنید، همهٔ secrets احتمالی را rotate
کنید، و policy/CI برای رد archiveهای حاوی `.env` یا الگوی credential بیفزایید.
فقط پاک‌کردن فایل از HEAD کافی نیست.

**تأیید پس از رفع:** اسکن تاریخچه و remote با secret scanner؛ سپس تأیید rotation
تمام credentialها بدون چاپ مقدارشان در log یا گزارش.

### P0-03 — migrationهای Article Agent در دیتابیس بررسی‌شده اعمال نشده‌اند

**کامنت ممیزی:** خروجی `showmigrations --plan` نشان می‌دهد
`article_agent.0003_execution_checkpoints` و `0004_article_brand_name` unapplied
هستند. کد production از هر دو فیلد استفاده می‌کند؛ بنابراین اجرای worker یا view
روی این schema می‌تواند به `column does not exist` برسد.

**شواهد:**
`apps/article_agent/migrations/0003_execution_checkpoints.py`،
`apps/article_agent/migrations/0004_article_brand_name.py`،
`apps/article_agent/models.py:63,89` و خروجی ممیزی `manage.py showmigrations
article_agent --plan` در تاریخ گزارش.

**اثر:** شکست ساخت مقاله، checkpoint و برند در محیطی که با همین migration plan
اجرا شود.

**پیشنهاد رفع:** قبل از deploy، backup و migration plan را روی clone دیتابیس
آزمون کنید؛ سپس `migrate` را به یک مرحلهٔ release اتمیک و قابل مشاهده تبدیل کنید.
Worker نباید پیش از کامل‌شدن migrationها شروع شود.

**تأیید پس از رفع:** `showmigrations --plan` بدون مورد unapplied و smoke test ساخت
یک job، ذخیرهٔ checkpoint و brand name روی همان دیتابیس release.

### P0-04 — quality gate واقعی نیست و خروجی ناموفق به عنوان completed منتشر می‌شود

**کامنت ممیزی:** دو check اصلی همیشه `True` هستند؛ failure در review بخش و failure
کل report فقط log warning می‌سازند. این رفتار با checklist و Master Spec که
می‌گویند review ناموفق و finding critical باید completion را متوقف کنند، تناقض
دارد. اگر سیاست محصول «تولید حتی با نمره کم» است، نام status نباید `completed`
بدون هشدار قابل مشاهده باشد.

**شواهد:**
`apps/article_agent/application/article_pipeline.py:99-130,454-470,501-542`؛
`docs/article-agent/MASTER_SPEC.md:53-58,73-75`؛
`docs/article-agent/ACCEPTANCE_CHECKLIST.md:79-89`.

**اثر:** خروجی فاقد حداقل کیفیت، با critical finding، تعداد کلمهٔ بسیار نامنطبق یا
review ناموفق می‌تواند به عنوان نتیجهٔ کامل به کاربر تحویل شود؛ برای محتوای فنی و
ایمنی‌محور خطر بالاست.

**پیشنهاد رفع:** دو وضعیت جدا تعریف کنید: `completed` فقط برای معیارهای hard
safety/schema و `completed_with_warnings` برای نقص‌های نرمِ مورد تأیید سیاست
محصول. critical safety/factual/schema را همچنان blocking نگه دارید. report،
هشدارها و دلیل چاپ اجباری را در UI و DOCX نشان دهید؛ checklist را با تصمیم نهایی
محصول هم‌راستا کنید.

**تأیید پس از رفع:** تست‌های جدا برای low-score قابل چاپ، critical finding غیرقابل
چاپ، FAQ نادرست غیرقابل چاپ و نمایش warning در dashboard.

## یافته‌های P1

### P1-01 — retry دستی خروجی اجرای قبلی را reuse می‌کند

**کامنت ممیزی:** retry فقط status و چند فیلد سطحی را reset می‌کند. `checkpoint_payload`,
`memory_payload`, `plan_payload`, `result_payload`, فایل خروجی و `ArticleSection`
های قبلی پاک یا version-scope نمی‌شوند. execution بعدی همهٔ sectionهایی را که
`review_payload.passed` دارند complete فرض می‌کند؛ query هم به
`execution_version` محدود نشده است. بنابراین «تلاش مجدد» ممکن است تقریباً هیچ
چیزی را دوباره تولید نکند و متن ناموفق قدیمی را تحویل دهد.

**شواهد:**
`apps/article_agent/presentation/web/views.py:87-99`،
`apps/article_agent/application/job_execution.py:53-59,139-153,162-165`،
`apps/article_agent/application/article_pipeline.py:246-255,318-330`.

**اثر:** retry کاربر semantic نیست، دادهٔ قدیمی با version جدید آمیخته می‌شود و
دیباگ/بازبینی غیرقابل اعتماد می‌گردد.

**پیشنهاد رفع:** retry دستی را به execution جدید immutable تبدیل کنید: تمام
artifactهای execution را یا version-key کنید یا به run مستقل منتقل کنید. policy
باید صریحاً «resume provider retry» را از «restart user retry» جدا کند. در restart
جدید checkpoint/memory/sections/output قبلی را reuse نکنید؛ در resume فقط
checkpointهای همان execution و دارای schema/version معتبر مجاز باشند.

**تأیید پس از رفع:** آزمون integration: failure بعد از section اول، retry دستی،
اثبات اینکه output/section/checkpoint نسخهٔ قبل خوانده نشده؛ و آزمون resume
provider بدون از دست‌دادن خروجی سالم.

### P1-02 — enqueue با تراکنش دیتابیس اتمیک نیست

**کامنت ممیزی:** job ابتدا در DB ساخته یا queued می‌شود و سپس خارج از transaction
به broker publish می‌شود. اگر `apply_async` خطا دهد، job دائماً queued می‌ماند ولی
هیچ taskی برای آن وجود ندارد. برعکس، انتشار بیرون از transactional outbox امکان
race با commit را ایجاد می‌کند.

**شواهد:** `apps/article_agent/presentation/web/views.py:26-38,61-64,87-99`.

**اثر:** job گم‌شده، UI با «در صف» دائمی و نیاز به مداخلهٔ دستی.

**پیشنهاد رفع:** وضعیت `enqueue_pending`، transactional outbox و dispatcher
idempotent بسازید؛ یا حداقل `transaction.on_commit` به همراه failure state و
re-enqueue watchdog داشته باشید. task identity باید فقط پس از publish موفق یا از
طریق outbox ثبت نهایی شود.

**تأیید پس از رفع:** تست broker exception، crash بین commit/publish و reaper برای
jobهای queued بدون task.

### P1-03 — timeout نرم Celery به failure قابل تشخیص/قابل resume تبدیل نشده است

**کامنت ممیزی:** task همهٔ exceptionها را generic handling می‌کند و برای
`SoftTimeLimitExceeded` policy ویژه‌ای ندارد. با توجه به soft limit شش ساعت،
interrupt در هر `await` ممکن است job را failed بگذارد، بدون checkpoint مرحلهٔ
نهایی و بدون راهنمای عملی برای کاربر.

**شواهد:** `apps/article_agent/tasks.py:79-130`،
`apps/article_agent/application/job_execution.py:82-95`،
`config/settings.py:160-170`.

**اثر:** همان خطایی که در production دیده شد به failure غیرشفاف، retry نامناسب یا
status باقی‌مانده در مرحلهٔ قبلی می‌انجامد.

**پیشنهاد رفع:** `billiard.exceptions.SoftTimeLimitExceeded` را جداگانه catch
کنید، cancellation/checkpoint-safe boundary تعریف کنید، status/error code ویژه
ثبت کنید و فقط وقتی resume واقعاً امن است retry کنید. soft/hard limit را فقط برای
queue article route اعمال کنید، نه همهٔ taskها.

**تأیید پس از رفع:** تست تزریق soft timeout در writing، review و render و بررسی
checkpoint، status و retry policy.

### P1-04 — محدودیت ۲۰٬۰۰۰ کلمه با وعدهٔ «هر تعداد کلمه» ناسازگار است

**کامنت ممیزی:** view درخواست بیشتر از `ARTICLE_AGENT_MAX_WORD_COUNT` را رد
می‌کند و مقدار پیش‌فرض آن ۲۰٬۰۰۰ است. برای هر مقدار بزرگ‌تر، پاسخ generic
`Provide valid article details` داده می‌شود، نه راهنمای قابل اقدام.

**شواهد:** `apps/article_agent/presentation/web/views.py:49-60`،
`config/settings.py:176-183`.

**اثر:** نیاز اعلام‌شده برای عدم گیرکردن در مقاله‌های بلندتر برآورده نشده و خطا
برای کاربر مبهم است.

**پیشنهاد رفع:** یک سقف محصولیِ صریح و مستند تعیین کنید یا pipeline را به chapter/
batchهای durable تقسیم کنید. اگر سقف برای هزینه/زمان لازم است، پیام دقیق شامل حد
فعلی، علت و روش split ارائه شود. هیچ‌وقت با بزرگ‌شدن prompt، context model را
دور نزنید.

**تأیید پس از رفع:** تست ۵k، ۱۰k، ۲۰k و یک درخواست بالاتر از سقف؛ برای هر کدام
حداکثر اندازهٔ prompt، completion و زمان/حافظه ثبت شود.

### P1-05 — context compaction می‌تواند به `{}` برسد و review را بی‌معنا کند

**کامنت ممیزی:** وقتی required fields در حد limit جا نشوند، fallback فقط کلیدهای
`task/section/budget/draft` را نگه می‌دارد؛ اگر representation این کلیدها را نداشته
باشد (مانند article review با `plan/sections/extras`) در نهایت `{}` برمی‌گردد.
همچنین `_compact` فقط سه عضو اول list را نگه می‌دارد. در مقاله‌های بلند، reviewer
ممکن است بدون prose/plan کافی پاسخ دهد؛ این با هدف «محدود اما واقعی» ناسازگار است.

**شواهد:** `apps/article_agent/application/context_builder.py:227-272,305-325`؛
`apps/article_agent/application/services.py:511-549`؛
`apps/article_agent/application/specialist_review.py:90-103`.

**اثر:** عدم پرشدن context با از دست‌رفتن خاموش دادهٔ حیاتی جایگزین می‌شود؛ نتیجهٔ
review قابل اعتماد نیست.

**پیشنهاد رفع:** برای هر operation schema حداقلیِ اختصاصی بسازید که هرگز حذف نشود
(heading/unit id/budget/مقتطف prose/critical facts). به جای `{}` یک
`ContextCompactionError` یا status ساختاریافته تولید کنید اگر minimum representation
جا نمی‌شود. کاهش باید field-aware و قابل مشاهده (اصل/نهایی bytes و fields dropped)
باشد.

**تأیید پس از رفع:** property/integration tests برای ورودی فارسی بسیار بزرگ و
assert روی valid JSON، وجود invariantها و نبود `{}`.

### P1-06 — Article reviewer به‌طور پیش‌فرض همهٔ sectionها را affected می‌کند

**کامنت ممیزی:** خروجی عادی reviewer plain text است. هر `REQUIRED FIXES` باعث یک
finding با `affected_units` شامل تمام sectionها می‌شود و FinalEditor همهٔ fixها را
به تک‌تک sectionهای affected اضافه می‌کند. فقط branch سازگاری JSON می‌تواند unit
دقیق نگه دارد، اما prompt عملاً JSON نمی‌خواهد.

**شواهد:** `apps/article_agent/application/services.py:551-637,679-705`.

**اثر:** خلاف «final editing targeted»؛ هزینه، ریسک تغییر بی‌دلیل، و زمینهٔ خطای
factual در همهٔ بخش‌ها افزایش می‌یابد.

**پیشنهاد رفع:** article review را به JSON schema معتبر با `affected_units` اجباری
تبدیل کنید؛ finding بدون unit را non-actionable/needs-human-review نگه دارید و فقط
fixهای همان unit را به editor بدهید.

**تأیید پس از رفع:** یک finding برای `section:2` فقط یک provider call editor داشته
باشد و سایر sectionها byte-for-byte حفظ شوند.

### P1-07 — تخصص‌سنجی‌های نامعتبر بی‌صدا به «غیرقابل‌اعمال» تبدیل می‌شوند

**کامنت ممیزی:** اگر پاسخ هر متخصص JSON معتبر نباشد، coordinator آن را به opinion
`applicable=False` تبدیل می‌کند و pipeline ادامه می‌دهد. در نتیجه ممکن است پنج
reviewer همگی fail کنند ولی مقاله بدون هیچ علامت failure نهایی شود. چرخهٔ پنج call
پیاپی نیز بین roleها cancellation check ندارد.

**شواهد:** `apps/article_agent/application/specialist_review.py:105-127,147-166,169-184`؛
`apps/article_agent/application/article_pipeline.py:598-606`.

**اثر:** کنترل‌های تخصصی ظاهری‌اند، failure مدل/ساختار پنهان می‌شود و cancel با
تاخیر زیاد پاسخ می‌گیرد.

**پیشنهاد رفع:** contract violation را با status `review_unavailable` در payload
ثبت کنید و policy صریح بگذارید: برای نقش‌های safety-critical یا retry محدود، یا
`completed_with_warnings` آشکار. callback cancellation را بین roleها بررسی کنید؛
roleهای فعال را در startup با مجموعهٔ مجاز validate کنید.

**تأیید پس از رفع:** آزمون JSON خراب برای یک نقش، همهٔ نقش‌ها و cancellation میان
نقش دوم/سوم؛ UI باید failure/warning هر نقش را نشان دهد.

### P1-08 — گردش چند API key shared cooldown ندارد

**کامنت ممیزی:** در TPD 429، call جاری کلیدهای موجود را به‌ترتیب امتحان می‌کند؛
اما هر call جدید از slot 1 شروع می‌شود و هیچ state مشترکی از exhausted بودن کلید
یا زمان reset نگه نمی‌دارد. پس بعد از پرشدن کلید اول، تمام callهای بعدی ابتدا یک
429 اضافی می‌خورند؛ بعد از exhausted شدن همهٔ کلیدها نیز retry Celery دوباره از
کلید 1 آغاز می‌شود. flag
`ARTICLE_AGENT_ENABLE_SECONDARY_API_KEY_FALLBACK` هم تعریف شده ولی استفاده نشده
است.

**شواهد:** `apps/article_agent/infrastructure/ai/groq_client.py:189-229,482-520`؛
`config/settings.py:311-315`.

**اثر:** اتلاف request/quota، تاخیر و log noise در زمان exhaustion و رفتار ناپایدار
چند worker.

**پیشنهاد رفع:** وضعیت credential (healthy/exhausted/retry_after) را بدون ذخیرهٔ
خود secret در Redis مشترک نگه دارید، slot سالم را atomically انتخاب کنید و زمان
reset/provider retry-after را رعایت کنید. فعال/غیرفعال بودن fallback را با setting
واقعاً enforce کنید.

**تأیید پس از رفع:** تست چند worker با slot 1 exhausted، انتخاب مستقیم slot 2 و
بازگشت کنترل‌شده به 1 پس از cooldown.

### P1-09 — قرارداد word budget متناقض و از نظر حسابداری نامعتبر می‌شود

**کامنت ممیزی:** تغییر عمدیِ اخیر برای عدم failure تعداد کلمه، prose خارج از
range را accept می‌کند. `consumed_words` سپس می‌تواند از `total_words` بالاتر رود
با اینکه domain invariant هنگام ساخت چنین وضعیتی را ممنوع می‌داند؛ quality gate
هم budget validity را `True` می‌گذارد. این انتخاب محصولی می‌تواند ادامه پیدا کند،
اما دیگر نباید با ادعای «hard runtime budget enforcement» مستند شود.

**شواهد:** `apps/article_agent/application/word_budget.py:55-158`؛
`apps/article_agent/domain/contracts.py:140-169`؛
`apps/article_agent/application/article_pipeline.py:104-130`.

**اثر:** report و remaining budget قابل اتکا نیست و واحدهای پایانی ممکن است با
بودجهٔ غیرواقعی تولید شوند.

**پیشنهاد رفع:** policy جدید را رسمی کنید: soft budget با سقف سختِ ایمنی، مقدار
delta per unit و article-level، و وضعیت warning. قبل از هر unit حداقل منابع
واحدهای باقی‌مانده را reserve کنید. فقط اختلاف نرم قابل قبول باشد؛ صفر/empty،
FAQ ناقص و تجاوز از safety cap همچنان باید failure باشند.

**تأیید پس از رفع:** test برای short/long permissible، تجاوز از hard cap، حفظ
minimumهای واحدهای باقیمانده و report دقیق delta.

### P1-10 — checkpoint فقط extras را دارد و render/final-state durable نیست

**کامنت ممیزی:** تنها checkpoint صریح، extras است. review نهایی، article review،
edited prose، metadata و document state checkpoint نمی‌شوند. شکست renderer یا
قطع worker پس از final edit باعث بازسازی چند مرحله‌ای و provider callهای تکراری
می‌شود؛ restore section نیز review واقعی را با `passed=True, score=10` جایگزین
می‌کند.

**شواهد:** `apps/article_agent/application/article_pipeline.py:248-255,377,380-583`؛
`apps/article_agent/application/job_execution.py:53-59,162-189`.

**اثر:** resume واقعی و idempotency به‌ویژه برای مقالهٔ بلند/گران تضمین نشده است.

**پیشنهاد رفع:** execution state machine و checkpoint schema versioned برای plan,
research, accepted units, actual reviews, final review, edited units, metadata و
render-ready article بسازید. render را idempotent و جدا از DB transaction/file
save کنید.

**تأیید پس از رفع:** crash injection پس از هر stage و اثبات اینکه resume فقط stage
ناقص را انجام می‌دهد و هیچ prose سالمی دوباره تولید نمی‌شود.

### P1-11 — Telegram entrypoint قطعاً ImportError می‌دهد و integration ناقص است

**کامنت ممیزی:** script ریشه `start_bot` را import می‌کند، اما module Telegram
فقط `TelegramBot` و `TelegramBotManager` دارد و تابعی با این نام وجود ندارد. bot
در هر پیام client LLM می‌سازد و آن را close نمی‌کند. همچنین config مدل دیتابیس
(`Chatbot` شامل model/key/base_url/system prompt/active) در مسیر واقعی مصرف
نمی‌شود؛ client همیشه global `.env` را می‌خواند.

**شواهد:** `run_telegram_bot.py:13-16`؛
`apps/social_media_chatbot/infrastructure/telegram/bot.py:41-106`؛
`apps/social_media_chatbot/infrastructure/ai/autogen_chatbot.py:7-55`؛
`apps/agents/models.py:18-65`.

**اثر:** سرویس Telegram شروع نمی‌شود؛ پس از رفع import نیز leak connection و
configuration اشتباه/نادیده‌گرفته‌شده رخ می‌دهد.

**پیشنهاد رفع:** یک management command رسمی بسازید که Chatbotهای active را از DB
load و validate کند، config را به client inject کند، lifecycle client را با
`finally: close()` مدیریت کند و graceful shutdown داشته باشد.

**تأیید پس از رفع:** smoke test import/command، تست دو bot با config متفاوت و
تست close شدن client در success/error.

### P1-12 — secrets chatbot به صورت plaintext در DB و admin قابل مشاهده‌اند

**کامنت ممیزی:** `api_key` و `telegram_bot_token` TextField هستند و در fieldset
admin مستقیماً editable‌اند. encryption-at-rest application-level، redaction یا
rotation workflow وجود ندارد.

**شواهد:** `apps/agents/models.py:41-52`؛ `apps/agents/admin.py:63-80`.

**اثر:** هر backup/DB read/admin compromise می‌تواند credential provider و
Telegram را افشا کند.

**پیشنهاد رفع:** secrets را در secret manager نگه دارید یا encrypted field با key
خارج از DB، masking در admin و audit log بدون مقدار secret استفاده کنید؛ rotation
و access policy را مستند کنید.

**تأیید پس از رفع:** test serialization/admin برای نبود secret در output و
exercise rotation بدون downtime.

## یافته‌های P2

### P2-01 — `python-docx` در requirements نیست

**کامنت ممیزی:** `DocxGenerator` مستقیماً `docx` را import می‌کند، ولی
`requirements.txt` هیچ `python-docx` ندارد. محیط فعلی آن را اتفاقی نصب دارد، پس
`pip check` نیز این omission را تشخیص نمی‌دهد.

**شواهد:** `apps/article_agent/infrastructure/document/docx_generator.py:1-7`؛
`requirements.txt`؛ `pip show python-docx` در محیط ممیزی.

**اثر:** deploy جدید می‌تواند هنگام render با `ModuleNotFoundError` شکست بخورد.

**پیشنهاد رفع:** dependency مستقیم را با نسخهٔ tested به requirements/lockfile
اضافه و clean-environment install + DOCX smoke test را در CI اجرا کنید.

### P2-02 — dependencies lock شده و قابل بازتولید نیستند

**کامنت ممیزی:** فایل dependencies ترکیبی از pin کامل و بازه‌های باز است، lockfile
ندارد، و بسته‌های هم‌پوشان/مشکوک مانند `httpcore` و `httpcore2`، `httpx` و
`httpx2` و همزمان `psycopg`/`psycopg-binary` دارد. نبود lint/type checker نصب‌شده
نیز دیده شد.

**شواهد:** `requirements.txt:1-75`؛ خروجی `Get-Command ruff,flake8,mypy` در
ممیزی خالی بود.

**اثر:** build غیرقطعی، dependency confusion/تداخل احتمالی و نبود کنترل کیفیت
پیش از deploy.

**پیشنهاد رفع:** dependency graph را کمینه کنید، packages غیرمعتبر/غیرضروری را
حذف کنید، `pip-tools`/Poetry/uv lockfile بسازید، hashes/SBOM و vulnerability scan
را CI کنید. ruff و pyright/mypy را در dev dependency اضافه کنید.

### P2-03 — error/logging ممکن است دادهٔ provider و محتوای کاربر را بیش‌ازحد افشا کند

**کامنت ممیزی:** 429 body تا ۲۰۰۰ کاراکتر log و در exception propagation قرار
می‌گیرد؛ task نیز detail را تا ۵۰۰ کاراکتر در DB/dashboard ذخیره می‌کند. specialist
review پاسخ خام را log می‌کند. تضمین redaction برای token، PII یا متن حساس وجود
ندارد.

**شواهد:** `apps/article_agent/infrastructure/ai/groq_client.py:530-579`؛
`apps/article_agent/tasks.py:20-23,106-129`؛
`apps/article_agent/application/specialist_review.py:117-125`.

**اثر:** نشت PII/محتوا/شناسه‌های provider در log، admin یا API status.

**پیشنهاد رفع:** یک sanitizer مرکزی با allowlist برای diagnostic fields، correlation
id، error code و safe summary بسازید. raw provider response را فقط پشت storage
امن و با TTL/role محدود نگه دارید.

### P2-04 — ذخیرهٔ فایل داخل transaction DB orphan file می‌سازد

**کامنت ممیزی:** `output_file.save` side-effect storage را قبل از commit DB انجام
می‌دهد. rollback یا crash بعد از save، file بی‌مرجع می‌گذارد؛ retry/replacement هم
cleanup نسخهٔ قبلی ندارد.

**شواهد:** `apps/article_agent/application/job_execution.py:180-189`.

**اثر:** افزایش storage، artifact اشتباه و دشواری cleanup.

**پیشنهاد رفع:** فایل را به staging با execution id بنویسید، DB را commit کنید و
در `on_commit` promote کنید؛ یا compensating cleanup و garbage collector
idempotent داشته باشید.

### P2-05 — metadata و نظرات متخصص در UI عملاً قابل استفاده نیستند

**کامنت ممیزی:** API status metadata و specialist reviews را می‌دهد، اما template
فقط table job را render می‌کند؛ metadata، warning، هر opinion/finding و source
قابل مشاهده/کپی/بازبینی نیست. نیاز کاربر برای «نظر دادن agentها» قابل audit توسط
کاربر نهایی نمی‌شود.

**شواهد:** `apps/article_agent/presentation/web/views.py:69-72`؛
`apps/article_agent/templates/article_agent/create_article.html:10-14`.

**اثر:** quality signal و meta output تولید می‌شود اما برای انتشار و رفع مشکل
کاربردی نیست.

**پیشنهاد رفع:** صفحهٔ جزئیات job با meta title/description، status generated vs
fallback، opinions/failures، quality report، warnings، نسخه و download ارائه
کنید؛ فقط owner بتواند ببیند.

### P2-06 — dashboard chatbot دادهٔ ساختگی نمایش می‌دهد و عملیات ندارد

**کامنت ممیزی:** view سه chatbot hard-coded برمی‌گرداند، با مدل DB هیچ query ندارد
و template چندین `href="#"` دارد. بنابراین صفحه مدیریت را القا می‌کند، اما state
واقعی را نمایش یا تغییر نمی‌دهد.

**شواهد:** `apps/dashboard/views.py:52-93`؛
`apps/dashboard/templates/dashboard/social_media_chatbots.html:89,390,412,478`؛
`apps/agents/models.py:18-65`.

**اثر:** dashboard گمراه‌کننده و feature نیمه‌کاره است.

**پیشنهاد رفع:** تا تکمیل CRUD، feature را از navigation مخفی/experimental کنید؛
سپس query واقعی، ownership/permission، فرم‌های POST+CSRF و integration test اضافه
کنید.

### P2-07 — logout با GET state را تغییر می‌دهد

**کامنت ممیزی:** مسیر logout برای GET است و view بدون `require_POST` session را
خاتمه می‌دهد.

**شواهد:** `apps/dashboard/urls.py:6-19`؛ `apps/dashboard/views.py:45-49`.

**اثر:** forced logout با لینک/تصویر third-party ممکن است؛ همچنین با policy امن
عملیات تغییر state ناسازگار است.

**پیشنهاد رفع:** logout را POST همراه CSRF کنید و لینک template را به فرم کوچک
تبدیل کنید.

### P2-08 — مدل identity و conversation در شرایط concurrent پایدار نیست

**کامنت ممیزی:** unique constraint شامل `bot_id=NULL` است؛ در PostgreSQL NULLها
distinct هستند، پس برای API می‌تواند duplicate user ایجاد شود. سپس
get-or-create conversation نیز transaction/unique constraint ندارد.

**شواهد:** `apps/social_media_chatbot/infrastructure/persistence/models.py:20-44,50-66`؛
`apps/social_media_chatbot/infrastructure/persistence/repositories/django_chat_memory.py:15-41`.

**اثر:** history split، duplicate conversation و پاسخ‌های غیرقابل پیش‌بینی در
request همزمان.

**پیشنهاد رفع:** bot_id را non-null sentinel کنید یا constraint مناسب PostgreSQL
با migration ایجاد کنید؛ conversation active را unique/lock و repository را در
transaction بازنویسی کنید.

### P2-09 — document/meta configuration ناقص است

**کامنت ممیزی:** Docx فقط article body/extras را می‌نویسد. اگر meta برای انتشار
وب لازم است، تنها در JSON result باقی می‌ماند و export قابل‌مصرفی ندارد. همچنین
fallback metadata ممکن است title را آن‌قدر truncate کند که title/brand طبیعی
نباشد؛ تنها طول max validate می‌شود.

**شواهد:** `apps/article_agent/application/seo_metadata.py:21-73`؛
`apps/article_agent/infrastructure/document/docx_generator.py:16-169`.

**اثر:** انتشار manual مستعد خطا و metadata fallback کم‌کیفیت است.

**پیشنهاد رفع:** تصمیم محصول را مستند کنید: meta فقط dashboard/API یا همراه export
separate. حداقل/کیفیت fallback، Unicode-safe truncate و user copy action اضافه
کنید.

### P2-10 — تنظیمات deployment و static file ناقص/rigid است

**کامنت ممیزی:** `ALLOWED_HOSTS` به یک IP hard-code شده، host/origin production از
env خوانده نمی‌شود و `STATIC_ROOT`/storage deployment configuration دیده نمی‌شود.
`check --deploy` نیز هشدار W009 را برای SECRET_KEY فعلی گزارش کرده است.

**شواهد:** `config/settings.py:27-41,143-149,356-403`؛ خروجی `manage.py check
--deploy` در ممیزی.

**اثر:** deploy دامنهٔ جدید، collectstatic، و security hardening شکننده است؛ کلید
فعلی از معیار Django برای production عبور نمی‌کند.

**پیشنهاد رفع:** validate settings typed، `DJANGO_ALLOWED_HOSTS` و trusted origins
از env، static/media strategy روشن، و enforcement طول/entropy secret در production.
کلید production را rotate کنید.

### P2-11 — token/context safety telemetry کافی ندارد

**کامنت ممیزی:** size context با heuristic bytes/2 و characters/4 محاسبه می‌شود و
وقتی quota امکان output مفید نداشته باشد می‌تواند به request با output بسیار کوچک
برسد. هیچ metric پایدار برای prompt bytes/tokens، fields dropped، output truncation
یا cost per job ذخیره نمی‌شود.

**شواهد:** `apps/article_agent/application/context_builder.py:52-80,180-182`؛
`apps/article_agent/application/services.py:46-82`؛
`apps/article_agent/infrastructure/ai/groq_client.py:242-249,342-411`.

**اثر:** خطای context/quota فقط پس از incident قابل تحلیل است و tuning ۵k+ کور
انجام می‌شود.

**پیشنهاد رفع:** per-operation metrics و structured events برای estimate/actual
usage، compaction, retry, credential slot (بدون secret)، elapsed time و final word
delta اضافه کنید؛ SLO و alert تعریف کنید.

## یافته‌های P3 و کد نیمه‌کاره/استفاده‌نشده

### P3-01 — WhatsApp adapter فایل خالی است

**کامنت ممیزی:** `apps/social_media_chatbot/infrastructure/whatsapp/bot.py` صفر
بایت است، با اینکه WhatsApp در choices مدل وجود دارد.

**پیشنهاد:** feature را از choices/UI حذف یا با adapter، webhook verification،
signature validation و test کامل implement کنید.

### P3-02 — route `apps.agents.urls` خالی است

**کامنت ممیزی:** `/api/` در URL root include شده اما `urlpatterns = []` است.

**شواهد:** `config/urls.py:25-35`؛ `apps/agents/urls.py:1-2`.

**پیشنهاد:** route را حذف کنید یا API واقعی versioned و مستند اضافه کنید.

### P3-03 — parser FAQ قدیمی و `count_faq_text` در production استفاده نمی‌شوند

**کامنت ممیزی:** production FAQ را با `generate_faq` تولید می‌کند، اما
`ArticlePipeline._parse_faq` و `WordCounter.count_faq_text` فقط legacy code/test
هستند. نگه‌داشتن دو قرارداد FAQ احتمال drift را زیاد می‌کند.

**شواهد:** `apps/article_agent/application/article_pipeline.py:356,644-669`؛
`apps/article_agent/application/word_budget.py:37-49`.

**پیشنهاد:** یا migration/compatibility policy را مستند و unit-test کنید، یا parser
قدیمی را حذف کنید و یک schema canonical داشته باشید.

### P3-04 — `request_payload` snapshot تولید را کنترل نمی‌کند

**کامنت ممیزی:** request در job ذخیره می‌شود اما execution از مدل `Article` می‌خواند.
در نتیجه snapshot به عنوان audit input وجود دارد ولی source of truth نیست.

**شواهد:** `apps/article_agent/presentation/web/views.py:61-63`؛
`apps/article_agent/application/job_execution.py:43-52`.

**پیشنهاد:** request payload immutable/versioned را canonical کنید یا آن را حذف کنید؛
هر تغییر article باید execution جدید ایجاد کند.

### P3-05 — documentation/status با واقعیت کد هم‌راستا نیست

**کامنت ممیزی:** acceptance checklist چند مورد سخت runtime budget و failed review
را تیک زده، اما code آن‌ها را advisory کرده است. Review Findings نیز مواردی را
resolved می‌خواند که برای Redis/Groq production هنوز verification خارجی لازم
دارد.

**شواهد:** `docs/article-agent/ACCEPTANCE_CHECKLIST.md:15-24,79-89,111-124`؛
`docs/article-agent/REVIEW_FINDINGS.md:14-23`؛
`apps/article_agent/application/word_budget.py:55-158`.

**پیشنهاد:** docs را versioned acceptance matrix کنید؛ هر تیک باید به test/integration
evidence و محیط verification لینک داشته باشد. تصمیم جدید «best-effort printable»
را صریح ثبت کنید.

## پوشش آزمون و شکاف‌های آن

موارد انجام‌شده در snapshot ممیزی:

- `python manage.py check` — موفق.
- `python manage.py makemigrations --check --dry-run` — موفق، بدون migration جدید.
- `python manage.py test --keepdb` — **۹۶ تست موفق**.
- `python -m compileall -q apps config` — موفق.
- `pip check` — موفق.
- `python manage.py check --deploy` — یک هشدار `security.W009` برای SECRET_KEY.
- `python manage.py showmigrations article_agent --plan` — `0003` و `0004`
  unapplied در دیتابیس بررسی‌شده.

نتیجهٔ مهم: ۹۶ تست موفق به‌معنای آماده‌بودن production نیست. تستی برای API چت،
Telegram entrypoint، broker/Redis واقعی، provider واقعی، schema دیتابیس release،
secret redaction، retry دستیِ versioned، soft timeout و مقاله‌های ۵k/۱۰k/۲۰k
وجود ندارد یا در suite کشف‌شده اجرا نشده است.

## ترتیب پیشنهادی رفع

1. **فوراً:** P0-02 (rotate/پاکسازی secrets)، P0-03 (migrate release)، P0-01
   (غیرفعال‌سازی endpoint یا رفع + auth/throttle)، P0-04 (policy کیفیت شفاف).
2. **دوام Article Agent:** P1-01، P1-02، P1-03 و P1-10؛ سپس crash-injection test.
3. **ایمنی context و محتوا:** P1-04 تا P1-09، با آزمون‌های ۵k/۱۰k/۲۰k و quality
status قابل مشاهده.
4. **سامانهٔ چت:** P1-11 و P1-12، سپس P2-06/P2-08.
5. **release hygiene:** P2-01/P2-02/P2-03/P2-10 و CI شامل lint/type/security.

تا پیش از پایان مرحلهٔ ۲، هیچ ادعای «مقاله‌های بلند بدون گیر و قابل resume» نباید
به عنوان تضمین production مطرح شود؛ تنها بعد از آزمایش واقعی روی همان Redis,
broker, DB و provider production می‌توان آن را تأیید کرد.
