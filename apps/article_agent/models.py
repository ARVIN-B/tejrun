from django.conf import settings
from django.db import models
from django.utils import timezone


class JobStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    PLANNING = "planning", "Planning"
    RESEARCHING = "researching", "Researching"
    WRITING = "writing", "Writing"
    REVIEWING = "reviewing", "Reviewing"
    REVISING = "revising", "Revising"
    FINAL_REVIEW = "final_review", "Final review"
    EDITING = "editing", "Editing"
    QUALITY_CHECK = "quality_check", "Quality check"
    RENDERING = "rendering", "Rendering"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCEL_REQUESTED = "cancel_requested", "Cancellation requested"
    CANCELLED = "cancelled", "Cancelled"

    @classmethod
    def active(cls) -> set[str]:
        return {
            cls.QUEUED, cls.PLANNING, cls.RESEARCHING, cls.WRITING, cls.REVIEWING,
            cls.REVISING, cls.FINAL_REVIEW, cls.EDITING, cls.QUALITY_CHECK,
            cls.RENDERING, cls.CANCEL_REQUESTED,
        }


class Article(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="articles")
    title = models.CharField(max_length=255)
    word_count = models.PositiveIntegerField()
    headings = models.JSONField(default=list)
    keywords = models.JSONField(default=list)
    language = models.CharField(max_length=16, default="fa")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)


class ArticleJob(models.Model):
    article = models.OneToOneField(Article, on_delete=models.CASCADE, related_name="job")
    status = models.CharField(max_length=32, choices=JobStatus.choices, default=JobStatus.QUEUED, db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)
    current_stage = models.CharField(max_length=255, default="Queued")
    current_section = models.PositiveSmallIntegerField(default=0)
    total_sections = models.PositiveSmallIntegerField(default=0)
    celery_task_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    request_payload = models.JSONField(default=dict)
    plan_payload = models.JSONField(default=dict, blank=True)
    memory_payload = models.JSONField(default=dict, blank=True)
    result_payload = models.JSONField(default=dict, blank=True)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.CharField(max_length=500, blank=True, default="")
    output_file = models.FileField(upload_to="article_outputs/%Y/%m/", blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def update_progress(self, status: str, progress: int, stage: str) -> None:
        self.status = status
        self.progress = max(self.progress, min(progress, 100))
        self.current_stage = stage
        self.save(update_fields=["status", "progress", "current_stage", "updated_at"])

    def mark_completed(self) -> None:
        self.status = JobStatus.COMPLETED
        self.progress = 100
        self.current_stage = "Completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "progress", "current_stage", "completed_at", "updated_at"])


class ArticleSection(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="sections")
    position = models.PositiveSmallIntegerField()
    heading = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    review_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("article", "position"), name="article_section_position_unique")]
        ordering = ("position",)
