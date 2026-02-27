# models/exceptions.py
"""Custom exceptions for the models pipeline.

Hierarchy:
    ModelsPipelineError
    +-- DataLoadError
    +-- FeatureEngineeringError
    +-- TrainingError
"""


class ModelsPipelineError(Exception):
    """Base exception for all errors in the models layer."""


class DataLoadError(ModelsPipelineError):
    """Raised when data loading fails (Parquet read, JSONL parse, splits)."""


class FeatureEngineeringError(ModelsPipelineError):
    """Raised when feature extraction or transformation fails."""


class TrainingError(ModelsPipelineError):
    """Raised when model training fails (XGBoost, Transformer)."""
