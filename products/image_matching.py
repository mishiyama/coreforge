import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.avif'}
STOPWORDS = {
    'and', 'by', 'edition', 'for', 'inch', 'model', 'new', 'series',
    'the', 'with', 'pro', 'plus', 'smart', 'wireless', 'black', 'white',
}


@dataclass(frozen=True)
class ImageCandidate:
    path: Path
    normalized_filename: str
    keywords: tuple[str, ...]
    extension: str
    size: int
    width: int | None
    height: int | None


@dataclass(frozen=True)
class ImageMatch:
    status: str
    candidate: ImageCandidate | None
    method: str
    score: int
    alternatives: tuple[ImageCandidate, ...] = ()


def normalize(value: str) -> str:
    value = Path(str(value)).stem.lower()
    return re.sub(r'[^a-z0-9]+', '', value)


def keywords(value: str) -> tuple[str, ...]:
    words = re.findall(r'[a-z0-9]+', str(value).lower())
    return tuple(
        word for word in words
        if (len(word) > 1 or word.isdigit()) and word not in STOPWORDS
    )


def inventory_images(image_dir: Path) -> list[ImageCandidate]:
    candidates = []
    for path in sorted(image_dir.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        width = height = None
        try:
            with Image.open(path) as image:
                width, height = image.size
        except Exception:
            pass
        candidates.append(ImageCandidate(
            path=path,
            normalized_filename=normalize(path.name),
            keywords=keywords(path.stem),
            extension=path.suffix.lower(),
            size=path.stat().st_size,
            width=width,
            height=height,
        ))
    return candidates


def match_image(name: str, brand: str, requested_filename: str,
                candidates: list[ImageCandidate]) -> ImageMatch:
    requested = Path(requested_filename).name.strip() if requested_filename else ''
    if requested:
        exact = [candidate for candidate in candidates
                 if candidate.path.name.lower() == requested.lower()]
        if len(exact) == 1:
            return ImageMatch('MATCHED', exact[0], 'exact filename', 100)
        if len(exact) > 1:
            return ImageMatch('AMBIGUOUS', None, 'exact filename', 100, tuple(exact))

    product_tokens = set(keywords(name))
    brand_tokens = set(keywords(brand))
    name_normalized = normalize(name)
    normalized = [candidate for candidate in candidates
                  if candidate.normalized_filename == name_normalized]
    if len(normalized) == 1:
        return ImageMatch('MATCHED', normalized[0], 'normalized product name', 90)
    if len(normalized) > 1:
        return ImageMatch('AMBIGUOUS', None, 'normalized product name', 90, tuple(normalized))

    scored = []
    product_model_tokens = {
        token for token in product_tokens
        if any(character.isdigit() for character in token)
    }

    for candidate in candidates:
        candidate_tokens = set(candidate.keywords)
        overlap = product_tokens & candidate_tokens
        brand_overlap = brand_tokens & candidate_tokens
        model_overlap = overlap - brand_tokens
        candidate_model_tokens = {
            token for token in candidate_tokens
            if any(character.isdigit() for character in token)
        }
        if brand_tokens and not brand_overlap:
            continue
        if product_model_tokens and candidate_model_tokens != product_model_tokens:
            continue
        if len(model_overlap) < 2 and not product_model_tokens:
            continue
        if not model_overlap:
            continue
        score = len(model_overlap) * 10 + len(brand_overlap) * 15
        if score >= 25:
            scored.append((score, candidate))

    scored.sort(key=lambda item: (-item[0], item[1].path.name.lower()))
    if not scored:
        return ImageMatch('UNMATCHED', None, 'no reliable evidence', 0)
    top_score = scored[0][0]
    top = [candidate for score, candidate in scored if score == top_score]
    if len(top) > 1:
        return ImageMatch('AMBIGUOUS', None, 'brand/model keywords', top_score, tuple(top))
    return ImageMatch('MATCHED', top[0], 'brand/model keywords', top_score)


def image_inventory_row(candidate: ImageCandidate) -> dict:
    return {
        'filename': candidate.path.name,
        'extension': candidate.extension,
        'file_size': candidate.size,
        'width': candidate.width,
        'height': candidate.height,
        'normalized_filename': candidate.normalized_filename,
        'possible_product_keywords': ','.join(candidate.keywords),
    }
