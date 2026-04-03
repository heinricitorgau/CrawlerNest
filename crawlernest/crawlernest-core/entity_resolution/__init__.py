from .types import EntityRecord, CanonicalProfile, ResolutionResult
from .alias_catalog import curated_alias_variants
from .normalizer import normalize_university_name
from .resolver import EntityResolver

__all__ = [
    "EntityRecord",
    "CanonicalProfile",
    "ResolutionResult",
    "curated_alias_variants",
    "normalize_university_name",
    "EntityResolver",
]
