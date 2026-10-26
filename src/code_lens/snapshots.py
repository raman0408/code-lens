"""Immutable capture and timeline analysis for student code attempts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .model import ChangeAttribution, analyze_versions


@dataclass(frozen=True)
class CodeSnapshot:
    sequence: int
    event: str
    captured_at: str
    source: str
    source_hash: str


@dataclass(frozen=True)
class SnapshotTransition:
    before: CodeSnapshot
    after: CodeSnapshot
    changes: tuple[ChangeAttribution, ...]
    analysis_error: str | None = None

    @property
    def score(self) -> int:
        """Total evidence score for this one student edit."""
        return sum(change.score for change in self.changes if change.is_meaningful)

    @property
    def is_meaningful(self) -> bool:
        return self.analysis_error is None and self.score > 0


@dataclass(frozen=True)
class TimelineAnalysis:
    snapshots: tuple[CodeSnapshot, ...]
    transitions: tuple[SnapshotTransition, ...]

    @property
    def best_improvement(self) -> SnapshotTransition | None:
        meaningful = [transition for transition in self.transitions if transition.is_meaningful]
        return max(meaningful, key=lambda item: (item.score, -item.after.sequence), default=None)


class SnapshotStore:
    """Local append-only store suitable for compile/submission hooks.

    A future platform can call :meth:`capture` whenever a compile or submission
    event occurs. Source is stored separately from metadata so every attempt is
    reproducible during assessment review.
    """

    MANIFEST = "manifest.json"

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    @property
    def manifest_path(self) -> Path:
        return self.directory / self.MANIFEST

    def capture(self, source: str, event: str) -> CodeSnapshot:
        if event not in {"compile", "submission"}:
            raise ValueError("event must be 'compile' or 'submission'")
        snapshots = list(self.load())
        sequence = len(snapshots) + 1
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        snapshot = CodeSnapshot(
            sequence=sequence,
            event=event,
            captured_at=datetime.now(timezone.utc).isoformat(),
            source=source,
            source_hash=digest,
        )
        self.directory.mkdir(parents=True, exist_ok=True)
        source_file = self.directory / f"{sequence:04d}-{digest[:12]}.py"
        source_file.write_text(source, encoding="utf-8")
        # Preserve existing source-file references.  Rebuilding the manifest from
        # loaded objects would lose the per-snapshot file names.
        manifest = [] if not self.manifest_path.exists() else json.loads(
            self.manifest_path.read_text(encoding="utf-8")
        )
        manifest.append({**self._to_manifest_entry(snapshot), "source_file": source_file.name})
        self.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return snapshot

    def load(self) -> tuple[CodeSnapshot, ...]:
        if not self.manifest_path.exists():
            return ()
        records = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        snapshots = []
        for record in records:
            source_path = self.directory / record["source_file"]
            snapshots.append(CodeSnapshot(
                sequence=record["sequence"], event=record["event"],
                captured_at=record["captured_at"], source=source_path.read_text(encoding="utf-8"),
                source_hash=record["source_hash"],
            ))
        return tuple(snapshots)

    @staticmethod
    def _to_manifest_entry(snapshot: CodeSnapshot) -> dict[str, object]:
        entry = asdict(snapshot)
        del entry["source"]
        return entry


def analyze_snapshots(snapshots: tuple[CodeSnapshot, ...] | list[CodeSnapshot]) -> TimelineAnalysis:
    """Analyze every consecutive edit and locate the strongest improvement."""
    ordered = tuple(sorted(snapshots, key=lambda item: item.sequence))
    transitions = tuple(_analyze_transition(before, after) for before, after in zip(ordered, ordered[1:]))
    return TimelineAnalysis(ordered, transitions)


def _analyze_transition(before: CodeSnapshot, after: CodeSnapshot) -> SnapshotTransition:
    try:
        return SnapshotTransition(before, after, tuple(analyze_versions(before.source, after.source)))
    except SyntaxError as error:
        message = f"cannot analyze invalid Python near line {error.lineno}"
        return SnapshotTransition(before, after, (), analysis_error=message)
