"""Evaluation helpers for measuring crawler/extractor quality against labels."""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from engine.extractor import (
    detect_internship,
    extract_all_with_rejections,
    load_keywords,
    normalize_target_category,
)
from engine.models import RawPage
from engine.scorer import score_opportunity

console = Console()


@dataclass
class EvalPrediction:
    url: str
    title: str
    true_should_save: bool
    pred_should_save: bool
    true_is_internship: bool
    pred_is_internship: bool
    true_role: Optional[str]
    pred_role: Optional[str]
    true_category: Optional[str]
    pred_category: Optional[str]
    score: int
    target_category: Optional[str] = None
    rejection_reason: Optional[str] = None

    @property
    def outcome(self) -> str:
        if self.true_should_save and self.pred_should_save:
            return "TP"
        if not self.true_should_save and self.pred_should_save:
            return "FP"
        if self.true_should_save and not self.pred_should_save:
            return "FN"
        return "TN"


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y", "ya", "valid", "save"}


def _normalize_label(value: object) -> Optional[str]:
    text = str(value or "").strip()
    if not text or text.lower() in {"null", "none", "-", "n/a"}:
        return None
    return text.lower().replace("-", "_").replace(" ", "_")


def _normalize_role(value: object) -> Optional[str]:
    role = _normalize_label(value)
    if not role:
        return None
    aliases = {
        "frontend_developer": "frontend",
        "software_engineering": "software_engineering",
        "backend_developer": "backend",
        "fullstack_developer": "fullstack",
        "mobile_developer": "mobile",
        "quality_assurance": "qa",
        "it_support": "it_support",
        "data_analyst": "data_analyst",
        "business_intelligence": "business_intelligence",
        "data_engineer": "data_engineer",
        "ai/ml_engineer": "ai_ml",
        "ai_ml_engineer": "ai_ml",
        "ui/ux_designer": "ui_ux",
        "ui_ux_designer": "ui_ux",
        "product_manager": "product",
        "actuarial": "actuarial",
    }
    return aliases.get(role, role)


def _prediction_from_row(
    row: dict,
    min_score: int,
    target_category: Optional[str] = None,
) -> EvalPrediction:
    url = row.get("url") or f"eval://{row.get('title', 'untitled')}"
    title = row.get("title") or ""
    row_target = normalize_target_category(row.get("target_category")) if row.get("target_category") else None
    active_target = row_target or normalize_target_category(target_category)
    text_parts = [
        title,
        row.get("company") or "",
        row.get("description") or "",
        row.get("raw_text") or "",
        row.get("true_location") or "",
    ]
    text = "\n".join(part for part in text_parts if part)
    pred_is_internship, _, _ = detect_internship(text, title, load_keywords())

    page = RawPage(
        url=url,
        title=title,
        text_content=text,
        html_content="",
        status_code=200,
        page_type="detail",
    )
    opportunities, rejections = extract_all_with_rejections([page], target_category=active_target)
    opp = opportunities[0] if opportunities else None
    if opp:
        opp = score_opportunity(opp)

    pred_should_save = bool(opp and opp.score >= min_score)
    pred_role = _normalize_role(opp.role if opp else None)
    pred_category = _normalize_label(opp.category if opp else None)
    rejection_reason = rejections[0].rejection_reason if rejections else None

    return EvalPrediction(
        url=url,
        title=title,
        true_should_save=_parse_bool(row.get("should_save")),
        pred_should_save=pred_should_save,
        true_is_internship=_parse_bool(row.get("true_is_internship")),
        pred_is_internship=pred_is_internship,
        true_role=_normalize_role(row.get("true_role")),
        pred_role=pred_role,
        true_category=_normalize_label(row.get("true_category")),
        pred_category=pred_category,
        score=opp.score if opp else 0,
        target_category=active_target,
        rejection_reason=rejection_reason,
    )


def _safe_div(num: int, den: int) -> float:
    return num / den if den else 0.0


def evaluate_dataset(
    dataset_path: str,
    min_score: int = 40,
    target_category: Optional[str] = None,
) -> dict:
    """Evaluate extractor/scorer output against a labeled CSV dataset."""
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    normalized_target = normalize_target_category(target_category)
    predictions = [
        _prediction_from_row(row, min_score, target_category=normalized_target)
        for row in rows
    ]
    tp = sum(1 for p in predictions if p.outcome == "TP")
    fp = sum(1 for p in predictions if p.outcome == "FP")
    fn = sum(1 for p in predictions if p.outcome == "FN")
    tn = sum(1 for p in predictions if p.outcome == "TN")

    internship_correct = sum(
        1 for p in predictions if p.true_is_internship == p.pred_is_internship
    )
    role_labeled = [
        p for p in predictions
        if p.true_should_save and p.pred_should_save and p.true_role is not None
    ]
    role_correct = sum(1 for p in role_labeled if p.true_role == p.pred_role)

    metrics = {
        "total": len(predictions),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": _safe_div(tp, tp + fp),
        "recall": _safe_div(tp, tp + fn),
        "internship_accuracy": _safe_div(internship_correct, len(predictions)),
        "role_accuracy": _safe_div(role_correct, len(role_labeled)),
        "target_category": normalized_target,
        "predictions": predictions,
    }
    return metrics


def print_eval_report(metrics: dict, show_errors: int = 20) -> None:
    """Render a compact CLI report for evaluation metrics."""
    console.rule("[bold cyan]MagangKareer Evaluation[/bold cyan]")
    console.print(f"Total samples: {metrics['total']}")
    if metrics.get("target_category"):
        console.print(f"Target category/role: [bold]{metrics['target_category']}[/bold]")
    console.print(
        "Precision: "
        f"[bold]{metrics['precision']:.2f}[/bold] | "
        f"Recall: [bold]{metrics['recall']:.2f}[/bold] | "
        f"Internship accuracy: [bold]{metrics['internship_accuracy']:.2f}[/bold] | "
        f"Role accuracy: [bold]{metrics['role_accuracy']:.2f}[/bold]"
    )
    console.print(
        f"TP={metrics['tp']} FP={metrics['fp']} "
        f"FN={metrics['fn']} TN={metrics['tn']}"
    )

    errors = [p for p in metrics["predictions"] if p.outcome in {"FP", "FN"}]
    role_errors = [
        p for p in metrics["predictions"]
        if p.outcome == "TP" and p.true_role and p.true_role != p.pred_role
    ]
    rows = errors + role_errors
    if not rows:
        console.print("\n[green][PASS][/green] No save/reject or role errors in this dataset.")
        return

    table = Table(title=f"Errors (showing {min(show_errors, len(rows))}/{len(rows)})")
    table.add_column("Type", width=5)
    table.add_column("Title", max_width=48)
    table.add_column("True Role", max_width=18)
    table.add_column("Pred Role", max_width=18)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Reason", max_width=24)

    for pred in rows[:show_errors]:
        err_type = pred.outcome
        if pred.outcome == "TP" and pred.true_role != pred.pred_role:
            err_type = "ROLE"
        table.add_row(
            err_type,
            pred.title[:48],
            pred.true_role or "-",
            pred.pred_role or "-",
            str(pred.score),
            pred.rejection_reason or "-",
        )

    console.print(table)
