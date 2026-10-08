"""Strict-but-forward-compatible serialization for Article Agent contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import (
    ArticleAllocation,
    ArticleBudget,
    ArticlePlan,
    ArticleRequest,
    ArticleReview,
    QualityReport,
    ResearchData,
    ReviewIssue,
    ReviewResult,
    SectionDraft,
    SectionPlan,
)


class ContractValidationError(ValueError):
    """Raised when external data cannot satisfy a domain contract."""


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{name} must be an object.")
    return value


def _list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractValidationError(f"{name} must be a list.")
    return value


def _string_list(data: Mapping[str, Any], key: str, default: list[str] | None = None) -> list[str]:
    value = data.get(key, default if default is not None else [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ContractValidationError(f"{key} must be a list of strings.")
    return value


def _required(data: Mapping[str, Any], key: str) -> Any:
    if key not in data:
        raise ContractValidationError(f"Missing required field: {key}.")
    return data[key]


def article_request_from_dict(value: object) -> ArticleRequest:
    data = _mapping(value, "ArticleRequest")
    try:
        return ArticleRequest(
            title=_required(data, "title"),
            word_count=_required(data, "word_count"),
            headings=_string_list(data, "headings"),
            keywords=_string_list(data, "keywords"),
            language=data.get("language", "fa"),
            audience=data.get("audience", "general"),
            tone=data.get("tone", "professional, natural, informative"),
            purpose=data.get("purpose", "inform"),
        )
    except (TypeError, ValueError) as error:
        raise ContractValidationError(str(error)) from error


def section_plan_from_dict(value: object) -> SectionPlan:
    data = _mapping(value, "SectionPlan")
    try:
        dependencies = _list(data.get("dependencies", []), "dependencies")
        if not all(isinstance(item, int) for item in dependencies):
            raise ContractValidationError("dependencies must be a list of integers.")
        return SectionPlan(
            index=_required(data, "index"),
            heading=_required(data, "heading"),
            purpose=_required(data, "purpose"),
            key_points=_string_list(data, "key_points"),
            target_words=_required(data, "target_words"),
            minimum_words=_required(data, "minimum_words"),
            maximum_words=_required(data, "maximum_words"),
            must_include=_string_list(data, "must_include"),
            must_avoid=_string_list(data, "must_avoid"),
            dependencies=dependencies,
            research_requirements=_string_list(data, "research_requirements"),
            keywords=_string_list(data, "keywords"),
        )
    except (TypeError, ValueError) as error:
        if isinstance(error, ContractValidationError):
            raise
        raise ContractValidationError(str(error)) from error


def article_budget_from_dict(value: object) -> ArticleBudget:
    data = _mapping(value, "ArticleBudget")
    try:
        allocations = []
        for value in _list(_required(data, "allocations"), "allocations"):
            allocation = _mapping(value, "allocation")
            allocations.append(ArticleAllocation(
                unit_id=_required(allocation, "unit_id"),
                unit_type=_required(allocation, "unit_type"),
                target_words=_required(allocation, "target_words"),
                minimum_words=_required(allocation, "minimum_words"),
                maximum_words=_required(allocation, "maximum_words"),
                priority=_required(allocation, "priority"),
                generated_words=allocation.get("generated_words", 0),
                status=allocation.get("status", "planned"),
            ))
        return ArticleBudget(
            total_words=_required(data, "total_words"), allocations=allocations,
            reserved_words=data.get("reserved_words", 0), consumed_words=data.get("consumed_words", 0),
        )
    except (TypeError, ValueError) as error:
        raise ContractValidationError(str(error)) from error


def article_plan_from_dict(value: object) -> ArticlePlan:
    data = _mapping(value, "ArticlePlan")
    try:
        sections = [section_plan_from_dict(item) for item in _list(_required(data, "sections"), "sections")]
        return ArticlePlan(
            title=_required(data, "title"),
            goal=_required(data, "goal"),
            audience=_required(data, "audience"),
            tone=_required(data, "tone"),
            language=_required(data, "language"),
            primary_topic=_required(data, "primary_topic"),
            keywords=_string_list(data, "keywords"),
            sections=sections,
            budget=article_budget_from_dict(_required(data, "budget")),
            global_constraints=_string_list(data, "global_constraints"),
            seo_intent=data.get("seo_intent", "informational"),
            coverage_requirements=_string_list(data, "coverage_requirements"),
        )
    except (TypeError, ValueError) as error:
        raise ContractValidationError(str(error)) from error


def review_result_from_dict(value: object) -> ReviewResult:
    data = _mapping(value, "ReviewResult")
    try:
        if not isinstance(_required(data, "passed"), bool):
            raise ContractValidationError("passed must be a boolean.")
        if not isinstance(_required(data, "score"), (int, float)):
            raise ContractValidationError("score must be a number.")
        raw_issues = _list(data.get("issues", []), "issues")
        issues = [
            ReviewIssue(
                type=_required(_mapping(item, "issue"), "type"),
                severity=_required(_mapping(item, "issue"), "severity"),
                description=_required(_mapping(item, "issue"), "description"),
            )
            for item in raw_issues
        ]
        return ReviewResult(
            passed=_required(data, "passed"),
            score=_required(data, "score"),
            issues=issues,
            strengths=_string_list(data, "strengths"),
            required_fixes=_string_list(data, "required_fixes"),
        )
    except (TypeError, ValueError) as error:
        raise ContractValidationError(str(error)) from error


def research_data_from_dict(value: object) -> ResearchData:
    data = _mapping(value, "ResearchData")
    try:
        return ResearchData(
            facts=_string_list(data, "facts"),
            statistics=_string_list(data, "statistics"),
            examples=_string_list(data, "examples"),
            claims=_string_list(data, "claims"),
            sources=_string_list(data, "sources"),
            confidence=data.get("confidence"),
        )
    except (TypeError, ValueError) as error:
        raise ContractValidationError(str(error)) from error


def section_draft_to_dict(draft: SectionDraft) -> dict[str, Any]:
    return {
        "section_index": draft.section_index,
        "heading": draft.heading,
        "content": draft.content,
        "word_count": draft.word_count,
        "revision_number": draft.revision_number,
    }


def article_plan_to_dict(plan: ArticlePlan) -> dict[str, Any]:
    return {
        "title": plan.title,
        "goal": plan.goal,
        "audience": plan.audience,
        "tone": plan.tone,
        "language": plan.language,
        "primary_topic": plan.primary_topic,
        "keywords": plan.keywords,
        "sections": [
            {
                "index": section.index,
                "heading": section.heading,
                "purpose": section.purpose,
                "key_points": section.key_points,
                "target_words": section.target_words,
                "minimum_words": section.minimum_words,
                "maximum_words": section.maximum_words,
                "must_include": section.must_include,
                "must_avoid": section.must_avoid,
                "dependencies": section.dependencies,
                "research_requirements": section.research_requirements,
                "keywords": section.keywords,
            }
            for section in plan.sections
        ],
        "budget": {
            "total_words": plan.budget.total_words,
            "reserved_words": plan.budget.reserved_words,
            "consumed_words": plan.budget.consumed_words,
            "allocations": [
                {
                    "unit_id": allocation.unit_id,
                    "unit_type": allocation.unit_type,
                    "target_words": allocation.target_words,
                    "minimum_words": allocation.minimum_words,
                    "maximum_words": allocation.maximum_words,
                    "priority": allocation.priority,
                    "generated_words": allocation.generated_words,
                    "status": allocation.status,
                }
                for allocation in plan.budget.allocations
            ],
        },
        "global_constraints": plan.global_constraints,
        "seo_intent": plan.seo_intent,
        "coverage_requirements": plan.coverage_requirements,
    }


def quality_report_to_dict(report: QualityReport) -> dict[str, Any]:
    return {
        "passed": report.passed,
        "target_word_count": report.target_word_count,
        "actual_word_count": report.actual_word_count,
        "tolerance": report.tolerance,
        "checks": report.checks,
        "warnings": report.warnings,
    }


def article_review_to_dict(review: ArticleReview) -> dict[str, Any]:
    return {
        "passed": review.passed,
        "score": review.score,
        "findings": [
            {
                "type": issue.type,
                "severity": issue.severity,
                "description": issue.description,
            }
            for issue in review.findings
        ],
        "section_scores": review.section_scores,
        "required_fixes": review.required_fixes,
    }
