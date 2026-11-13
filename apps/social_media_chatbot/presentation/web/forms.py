from django import forms
from django.conf import settings
from django.core.validators import URLValidator
from apps.agents.models import Chatbot


class ChatbotForm(forms.ModelForm):
    platform_api_key = forms.CharField(
        label="کلید اتصال پلتفرم",
        required=False,
        strip=True,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="در ویرایش خالی بماند تا کلید ذخیره‌شده حفظ شود.",
    )
    knowledge_file = forms.FileField(
        label="فایل دانش Markdown (اختیاری)",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": ".md,text/markdown,text/plain"}),
    )

    class Meta:
        model = Chatbot
        fields = (
            "name",
            "social_media",
            "brand_name",
            "system_prompt",
            "website_url",
        )
        labels = {
            "name": "نام بات",
            "social_media": "پلتفرم",
            "brand_name": "نام برند",
            "system_prompt": "پرامپت بات",
            "website_url": "آدرس سایت (اختیاری)",
        }
        widgets = {
            "system_prompt": forms.Textarea(attrs={"rows": 6}),
            "website_url": forms.URLInput(attrs={"dir": "ltr"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial["social_media"] = "telegram"
        self.fields["social_media"].choices = Chatbot.SOCIAL_MEDIA_CHOICES
        if self.instance.pk:
            self.fields["social_media"].disabled = True
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_platform_api_key(self):
        value = self.cleaned_data.get("platform_api_key", "")
        return value

    def clean_website_url(self):
        value = self.cleaned_data.get("website_url", "").strip()
        if value:
            URLValidator(schemes=("https",))(value)
        return value

    def clean_knowledge_file(self):
        uploaded = self.cleaned_data.get("knowledge_file")
        if uploaded:
            if not uploaded.name.lower().endswith(".md"):
                raise forms.ValidationError("فقط فایل با پسوند .md پذیرفته می‌شود.")
            if uploaded.size > 2 * 1024 * 1024:
                raise forms.ValidationError("حجم فایل Markdown نباید بیشتر از ۲ مگابایت باشد.")
        return uploaded

    def clean(self):
        cleaned = super().clean()
        platform = cleaned.get("social_media")
        if platform == "telegram":
            token = cleaned.get("platform_api_key")
            if not token and not self.instance.platform_api_key:
                self.add_error("platform_api_key", "توکن Telegram Bot الزامی است.")
        elif platform == "whatsapp":
            if not settings.SOCIAL_MEDIA_CHATBOT_EVOLUTION_API_KEY:
                self.add_error(None, "کلید سراسری Evolution باید در env اختصاصی سرور تنظیم شود.")
            if not settings.SOCIAL_MEDIA_CHATBOT_PUBLIC_BASE_URL:
                self.add_error(None, "آدرس عمومی HTTPS برای webhook باید در env اختصاصی تنظیم شود.")
        if not all((
            settings.SOCIAL_MEDIA_CHATBOT_LLM_API_KEY,
            settings.SOCIAL_MEDIA_CHATBOT_DEFAULT_MODEL,
            settings.SOCIAL_MEDIA_CHATBOT_DEFAULT_BASE_URL,
        )):
            self.add_error(None, "تنظیمات مدل هوش مصنوعی باید در فایل env اختصاصی Social Chatbot کامل شود.")
        if not settings.SOCIAL_MEDIA_CHATBOT_ENCRYPTION_KEY:
            self.add_error(None, "کلید رمزگذاری بات‌ها را در SOCIAL_MEDIA_CHATBOT_ENCRYPTION_KEY تنظیم کن.")
        return cleaned

    def save(self, commit=True):
        chatbot = super().save(commit=False)
        platform_api_key = self.cleaned_data.get("platform_api_key")
        if chatbot.social_media == "telegram":
            if platform_api_key:
                chatbot.platform_api_key = platform_api_key
            chatbot.telegram_bot_token = chatbot.platform_api_key
        chatbot.model = settings.SOCIAL_MEDIA_CHATBOT_DEFAULT_MODEL
        chatbot.base_url = settings.SOCIAL_MEDIA_CHATBOT_DEFAULT_BASE_URL
        upload = self.cleaned_data.get("knowledge_file")
        if upload:
            chatbot.knowledge_markdown = upload.read().decode("utf-8-sig")
        if commit:
            chatbot.save()
            self.save_m2m()
        return chatbot
