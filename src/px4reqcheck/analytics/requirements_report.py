"""Generate the requirement traceability matrix and HTML reports."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from jinja2 import Environment, FileSystemLoader, select_autoescape

from px4reqcheck.analytics.evaluation import evaluate_corpus, verdict_records
from px4reqcheck.analytics.report import generate_static_figures
from px4reqcheck.requirements.evaluate import NotEvaluableCause

CAUSES: tuple[NotEvaluableCause, ...] = (
    "param_missing",
    "param_disabled",
    "param_changed_in_flight",
    "signal_missing",
    "window_missing",
    "insufficient_samples",
    "quality_fail",
)


def generate_requirements_report(
    data_root: Path,
    output: Path,
    manifest_path: Path = Path("corpus/manifest.json"),
) -> dict[str, Path]:
    verdicts, resolved_signals = evaluate_corpus(data_root)
    records = verdict_records(verdicts)
    if not records:
        raise ValueError(f"no log partitions found in {data_root}")
    output.mkdir(parents=True, exist_ok=True)
    verdict_frame = pd.DataFrame(records)
    matrix = _traceability_matrix(verdict_frame)
    verdict_path = output / "verdicts.json"
    verdict_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    matrix_path = output / "traceability.csv"
    matrix.to_csv(matrix_path, index=False)
    pd.DataFrame(resolved_signals).to_csv(output / "resolved-signals.csv", index=False)
    plotly_path = output / "traceability.html"
    _write_plotly(verdict_frame, plotly_path)
    figures = generate_static_figures(data_root, output / "assets")
    report_path = output / "index.html"
    _write_report(matrix, verdict_frame, manifest_path, report_path)
    return {
        "verdicts": verdict_path,
        "matrix": matrix_path,
        "plotly": plotly_path,
        "report": report_path,
        "quality_figure": figures[0],
        "firmware_figure": figures[1],
    }


def _traceability_matrix(verdicts: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for requirement_id, group in verdicts.groupby("requirement_id", sort=True):
        not_evaluable = group["status"] == "not_evaluable"
        row: dict[str, Any] = {
            "requirement_id": requirement_id,
            "total": len(group),
            "evaluable": int((~not_evaluable).sum()),
            "pass": int((group["status"] == "pass").sum()),
            "fail": int((group["status"] == "fail").sum()),
            "not_evaluable": int(not_evaluable.sum()),
        }
        for cause in CAUSES:
            row[cause] = int((group["cause"] == cause).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def _write_plotly(verdicts: pd.DataFrame, output: Path) -> None:
    display = verdicts[
        [
            "log_id",
            "requirement_id",
            "status",
            "metric_value",
            "comparator",
            "threshold_value",
            "unit",
            "cause",
        ]
    ].fillna("")
    figure = go.Figure(
        data=[
            go.Table(
                header={
                    "values": list(display.columns),
                    "fill_color": "#16324f",
                    "font": {"color": "white"},
                },
                cells={"values": [display[column] for column in display.columns], "align": "left"},
            )
        ]
    )
    figure.update_layout(title="Per-log requirement drill-down", height=900)
    figure.write_html(
        output,
        include_plotlyjs="cdn",
        full_html=True,
        div_id="traceability-table",
    )


def _write_report(
    matrix: pd.DataFrame,
    verdicts: pd.DataFrame,
    manifest_path: Path,
    output: Path,
) -> None:
    environment = Environment(
        loader=FileSystemLoader(Path(__file__).with_name("templates")),
        autoescape=select_autoescape(["html"]),
    )
    template = environment.get_template("requirements.html")
    total = len(verdicts)
    evaluable = int((verdicts["status"] != "not_evaluable").sum())
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    output.write_text(
        template.render(
            matrix=matrix.to_dict(orient="records"),
            total=total,
            evaluable=evaluable,
            log_count=len(manifest["logs"]),
            manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        ),
        encoding="utf-8",
    )
