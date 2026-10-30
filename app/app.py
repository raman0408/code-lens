"""Run the local Code Lens teacher demonstration application."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for

from code_lens.engine import analyze_attempt
from code_lens.evaluation import evaluate_source
from code_lens.ml import LogisticRegressionModel
from code_lens.snapshots import SnapshotStore

if __package__:
    from .database import connect
    from .problems import BY_SLUG, PROBLEMS
else:  # Supports `python app/app.py` as well as `python -m app.app`.
    from database import connect
    from problems import BY_SLUG, PROBLEMS


def create_app(test_config: dict[str, object] | None = None) -> Flask:
    application = Flask(__name__, instance_relative_config=True)
    application.config.from_mapping(
        SECRET_KEY="local-demo-only",
        DATABASE=str(Path(application.instance_path) / "code_lens.db"),
        ATTEMPT_ROOT=str(ROOT / ".code-lens" / "web-attempts"),
        MODEL_PATH=str(ROOT / "models" / "synthetic-ml-ranker.json"),
    )
    if test_config:
        application.config.update(test_config)
    Path(application.instance_path).mkdir(parents=True, exist_ok=True)
    Path(application.config["ATTEMPT_ROOT"]).mkdir(parents=True, exist_ok=True)

    def db() -> sqlite3.Connection:
        if "db" not in g:
            g.db = connect(Path(application.config["DATABASE"]))
        return g.db

    @application.teardown_appcontext
    def close_db(_: object) -> None:
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    def attempt_or_404(attempt_id: int) -> sqlite3.Row:
        row = db().execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,)).fetchone()
        if row is None:
            abort(404)
        return row

    @application.get("/")
    def dashboard():
        attempts = db().execute("SELECT * FROM attempts ORDER BY id DESC").fetchall()
        return render_template("dashboard.html", problems=PROBLEMS, attempts=attempts)

    @application.post("/attempts")
    def create_attempt():
        student_name = request.form.get("student_name", "").strip()
        problem_slug = request.form.get("problem_slug", "")
        if not student_name or problem_slug not in BY_SLUG:
            flash("Choose a problem and enter a student name.", "error")
            return redirect(url_for("dashboard"))
        cursor = db().execute("INSERT INTO attempts(student_name, problem_slug, store_path) VALUES (?, ?, ?)",
                              (student_name, problem_slug, "pending"))
        attempt_id = cursor.lastrowid
        store_path = Path(application.config["ATTEMPT_ROOT"]) / f"attempt-{attempt_id:04d}"
        db().execute("UPDATE attempts SET store_path = ? WHERE id = ?", (str(store_path), attempt_id))
        db().commit()
        return redirect(url_for("workspace", attempt_id=attempt_id))

    @application.get("/attempts/<int:attempt_id>")
    def workspace(attempt_id: int):
        attempt = attempt_or_404(attempt_id)
        problem = BY_SLUG[attempt["problem_slug"]]
        snapshots = SnapshotStore(Path(attempt["store_path"])).load()
        initial_code = snapshots[-1].source if snapshots else problem.starter_code
        return render_template("workspace.html", attempt=attempt, problem=problem, code=initial_code,
                               snapshots=snapshots)

    @application.post("/attempts/<int:attempt_id>/action")
    def attempt_action(attempt_id: int):
        attempt = attempt_or_404(attempt_id)
        action = request.form.get("action")
        source = request.form.get("source", "")
        if action not in {"compile", "run", "submit"} or not source.strip():
            flash("Code and a valid action are required.", "error")
            return redirect(url_for("workspace", attempt_id=attempt_id))
        event = "submission" if action == "submit" else action
        snapshot = SnapshotStore(Path(attempt["store_path"])).capture(source, event)
        evaluation = evaluate_source(source, BY_SLUG[attempt["problem_slug"]].spec)
        if action == "submit":
            db().execute("UPDATE attempts SET status = 'submitted' WHERE id = ?", (attempt_id,))
            db().commit()
            return redirect(url_for("report", attempt_id=attempt_id))
        message = (f"Version {snapshot.sequence}: {evaluation.passed}/{evaluation.total} public tests passed"
                   if evaluation.error is None else f"Version {snapshot.sequence}: {evaluation.error}")
        flash(message, "success" if evaluation.is_correct else "error")
        return redirect(url_for("workspace", attempt_id=attempt_id))

    @application.get("/attempts/<int:attempt_id>/report")
    def report(attempt_id: int):
        attempt = attempt_or_404(attempt_id)
        problem = BY_SLUG[attempt["problem_slug"]]
        model_path = Path(application.config["MODEL_PATH"])
        model = LogisticRegressionModel.load(model_path) if model_path.exists() else None
        analysis = analyze_attempt(
            Path(attempt["store_path"]), problem.spec, model,
            allow_implementation_improvements=True,
        )
        snapshots = SnapshotStore(Path(attempt["store_path"])).load()
        selected = analysis.selected_transition
        before = next((item for item in snapshots if selected and item.sequence == selected[0]), None)
        after = next((item for item in snapshots if selected and item.sequence == selected[1]), None)
        return render_template("report.html", attempt=attempt, problem=problem, analysis=analysis,
                               snapshots=snapshots, before=before, after=after)

    return application


if __name__ == "__main__":
    create_app().run(debug=True)
