"""Deterministic source-code change analysis."""

from .model import ChangeAttribution, ProgramAnalysis, analyze_versions
from .snapshots import CodeSnapshot, SnapshotStore, TimelineAnalysis, analyze_snapshots
from .ml import LogisticRegressionModel
from .ranking import RankedTransition, TimelineRanking, rank_timeline, rank_timeline_with_model
from .engine import AttemptAnalysis, analyze_attempt

__all__ = ["ChangeAttribution", "ProgramAnalysis", "analyze_versions", "CodeSnapshot",
           "SnapshotStore", "TimelineAnalysis", "analyze_snapshots", "LogisticRegressionModel",
           "RankedTransition", "TimelineRanking", "rank_timeline", "rank_timeline_with_model",
           "AttemptAnalysis", "analyze_attempt"]
