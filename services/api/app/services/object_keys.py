from __future__ import annotations

import re
from dataclasses import dataclass

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")


def _segment(value: str, label: str) -> str:
    if not _SAFE_SEGMENT.fullmatch(value):
        raise ValueError(f"{label} must be a safe object-key segment")
    return value


@dataclass(frozen=True, slots=True)
class ObjectKeys:
    """The private, PRD-defined B2 key layout for one Fit Check tenant."""

    prefix: str

    def __post_init__(self) -> None:
        normalized = self.prefix.strip("/")
        if not normalized or ".." in normalized:
            raise ValueError("prefix must be a safe, non-empty path")
        object.__setattr__(self, "prefix", normalized)

    def _user_root(self, user_id: str) -> str:
        return f"{self.prefix}/users/{_segment(user_id, 'user_id')}"

    def upload_original(self, user_id: str, upload_id: str, extension: str) -> str:
        return (
            f"{self._user_root(user_id)}/uploads/{_segment(upload_id, 'upload_id')}/"
            f"original.{_segment(extension.lower().lstrip('.'), 'extension')}"
        )

    def upload_normalized(self, user_id: str, upload_id: str) -> str:
        return (
            f"{self._user_root(user_id)}/uploads/{_segment(upload_id, 'upload_id')}/normalized.jpg"
        )

    def model_profile_reference(self, user_id: str, profile_id: str, extension: str) -> str:
        """Keep personal try-on reference photos separate from wardrobe media."""

        return (
            f"{self._user_root(user_id)}/profiles/{_segment(profile_id, 'profile_id')}/"
            f"reference.{_segment(extension.lower().lstrip('.'), 'extension')}"
        )

    def candidate_source_crop(self, user_id: str, upload_id: str, candidate_id: str) -> str:
        """Keep pre-approval evidence under the upload that produced it.

        A candidate does not yet have a canonical garment ID, so this avoids
        pretending an unreviewed extraction is already wardrobe inventory.
        """

        return (
            f"{self._user_root(user_id)}/uploads/{_segment(upload_id, 'upload_id')}/"
            f"candidates/{_segment(candidate_id, 'candidate_id')}/source-crop.jpg"
        )

    def garment_source_crop(self, user_id: str, garment_id: str, crop_id: str) -> str:
        return (
            f"{self._user_root(user_id)}/garments/{_segment(garment_id, 'garment_id')}/"
            f"source-crops/{_segment(crop_id, 'crop_id')}.jpg"
        )

    def garment_mask(self, user_id: str, garment_id: str, mask_id: str) -> str:
        return (
            f"{self._user_root(user_id)}/garments/{_segment(garment_id, 'garment_id')}/"
            f"masks/{_segment(mask_id, 'mask_id')}.png"
        )

    def garment_cutout(self, user_id: str, garment_id: str, version: int) -> str:
        if version < 1:
            raise ValueError("version must be positive")
        return (
            f"{self._user_root(user_id)}/garments/"
            f"{_segment(garment_id, 'garment_id')}/cutouts/{version}.png"
        )

    def garment_thumbnail(self, user_id: str, garment_id: str, version: int) -> str:
        if version < 1:
            raise ValueError("version must be positive")
        return (
            f"{self._user_root(user_id)}/garments/"
            f"{_segment(garment_id, 'garment_id')}/thumbnails/{version}.webp"
        )

    def look_render(self, user_id: str, look_id: str, version: int) -> str:
        if version < 1:
            raise ValueError("version must be positive")
        return (
            f"{self._user_root(user_id)}/looks/{_segment(look_id, 'look_id')}/renders/{version}.png"
        )

    def look_thumbnail(self, user_id: str, look_id: str, version: int) -> str:
        if version < 1:
            raise ValueError("version must be positive")
        return (
            f"{self._user_root(user_id)}/looks/"
            f"{_segment(look_id, 'look_id')}/thumbnails/{version}.webp"
        )

    def manifest(self, user_id: str, run_id: str) -> str:
        return f"{self._user_root(user_id)}/manifests/{_segment(run_id, 'run_id')}.json"

    def export(self, user_id: str, export_id: str) -> str:
        return f"{self._user_root(user_id)}/exports/{_segment(export_id, 'export_id')}.zip"
