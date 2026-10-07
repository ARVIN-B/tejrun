from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from apps.article_agent.models import Article, ArticleJob, JobStatus
from apps.article_agent.tasks import generate_article_task


def _keywords(raw):
    result, seen = [], set()
    for value in raw.split("-"):
        value = " ".join(value.split())
        if value and value.casefold() not in seen:
            seen.add(value.casefold()); result.append(value)
    return result


def _owned(request, job_id):
    return get_object_or_404(ArticleJob.objects.select_related("article"), pk=job_id, article__owner=request.user)


@login_required
def create_article_view(request):
    return render(request, "article_agent/create_article.html", {"jobs": ArticleJob.objects.select_related("article").filter(article__owner=request.user)})


@require_POST
@login_required
def create_article_job(request):
    title = request.POST.get("title", "").strip()
    headings = [" ".join(value.split()) for value in request.POST.getlist("headings") if value.strip()]
    keywords = _keywords(request.POST.get("keywords", ""))
    try: word_count = int(request.POST.get("word_count", ""))
    except ValueError: return JsonResponse({"success": False, "error": "Word count must be a number."}, status=400)
    if not title or len(title) > 255 or not headings or len(headings) > settings.ARTICLE_AGENT_MAX_HEADINGS or any(len(heading) > settings.ARTICLE_AGENT_MAX_HEADING_LENGTH for heading in headings) or len({heading.casefold() for heading in headings}) != len(headings) or not 100 <= word_count <= settings.ARTICLE_AGENT_MAX_WORD_COUNT:
        return JsonResponse({"success": False, "error": "Provide valid article details."}, status=400)
    if len(keywords) > settings.ARTICLE_AGENT_MAX_KEYWORDS or any(len(item) > settings.ARTICLE_AGENT_MAX_KEYWORD_LENGTH for item in keywords):
        return JsonResponse({"success": False, "error": "Too many or overly long keywords."}, status=400)
    article = Article.objects.create(owner=request.user, title=title, word_count=word_count, headings=headings, keywords=keywords)
    job = ArticleJob.objects.create(article=article, total_sections=len(headings), request_payload={"title": title, "word_count": word_count, "headings": headings, "keywords": keywords})
    task = generate_article_task.apply_async(args=[job.pk], queue="article_generation")
    job.celery_task_id = task.id; job.save(update_fields=["celery_task_id", "updated_at"])
    return JsonResponse({"success": True, "job_id": job.pk, "status": job.status}, status=201)


@require_GET
@login_required
def job_status(request, job_id):
    job = _owned(request, job_id)
    return JsonResponse({"id": job.pk, "title": job.article.title, "keywords": job.article.keywords, "word_count": job.article.word_count, "status": job.status, "progress": job.progress, "current_stage": job.current_stage, "current_section": job.current_section, "total_sections": job.total_sections, "error_message": job.error_message, "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat(), "download_available": job.status == JobStatus.COMPLETED and bool(job.output_file)})


@require_POST
@login_required
def cancel_job(request, job_id):
    job = _owned(request, job_id)
    if job.status == JobStatus.QUEUED: job.status, job.current_stage = JobStatus.CANCELLED, "Cancelled"
    elif job.status in JobStatus.active(): job.status, job.current_stage = JobStatus.CANCEL_REQUESTED, "Cancellation requested"
    else: return JsonResponse({"success": False, "error": "This job cannot be cancelled."}, status=409)
    job.save(update_fields=["status", "current_stage", "updated_at"]); return JsonResponse({"success": True, "status": job.status})


@require_POST
@login_required
def retry_job(request, job_id):
    job = _owned(request, job_id)
    if job.status not in {JobStatus.FAILED, JobStatus.CANCELLED}: return JsonResponse({"success": False, "error": "This job cannot be retried."}, status=409)
    job.status, job.progress, job.current_stage, job.error_message, job.error_code = JobStatus.QUEUED, 0, "Queued", "", ""
    task = generate_article_task.apply_async(args=[job.pk], queue="article_generation")
    job.celery_task_id = task.id; job.save(); return JsonResponse({"success": True, "status": job.status})


@require_GET
@login_required
def download_job(request, job_id):
    job = _owned(request, job_id)
    if job.status != JobStatus.COMPLETED or not job.output_file: raise Http404("Output is not available.")
    return FileResponse(job.output_file.open("rb"), as_attachment=True, filename=f"article-{job.article_id}.docx")
