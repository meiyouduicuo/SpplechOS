"""Resolve local banner artwork before the shell exporter replaces its mirror."""
from pathlib import Path

EXTENSIONS=('png','jpg','jpeg','heic','webp')

def select_banner(framework, explicit=None, cached_paths=()):
    if explicit is not None:
        selected=Path(explicit)
        if not selected.is_file() or selected.suffix.lower().lstrip('.') not in EXTENSIONS:
            raise ValueError('The selected banner is missing or has an unsupported image extension')
        return selected
    candidates=[Path(p) for p in cached_paths if p]
    candidates.extend(Path(framework)/f'banner.{ext}' for ext in EXTENSIONS)
    return next((p for p in candidates if p.is_file() and p.suffix.lower().lstrip('.') in EXTENSIONS),None)
