from .types import EntityRecord, CanonicalProfile, ResolutionResult
from .normalizer import normalize_university_name
from .resolver import EntityResolver

__all__ = [
    "EntityRecord",
    "CanonicalProfile",
    "ResolutionResult",
    "normalize_university_name",
    "EntityResolver",
]
