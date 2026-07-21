import pytest

from app.services.object_keys import ObjectKeys


def test_prd_object_keys_are_stable() -> None:
    keys = ObjectKeys("fit-check")
    assert keys.upload_original("user-1", "upload-1", ".HEIC") == (
        "fit-check/users/user-1/uploads/upload-1/original.heic"
    )
    assert keys.upload_normalized("user-1", "upload-1") == (
        "fit-check/users/user-1/uploads/upload-1/normalized.jpg"
    )
    assert keys.model_profile_reference("user-1", "profile-1", ".PNG") == (
        "fit-check/users/user-1/profiles/profile-1/reference.png"
    )
    assert keys.garment_cutout("user-1", "garment-1", 2) == (
        "fit-check/users/user-1/garments/garment-1/cutouts/2.png"
    )
    assert keys.look_render("user-1", "look-1", 1) == (
        "fit-check/users/user-1/looks/look-1/renders/1.png"
    )
    assert keys.manifest("user-1", "run-1") == "fit-check/users/user-1/manifests/run-1.json"


@pytest.mark.parametrize("unsafe", ["../user", "user/name", "", "user name"])
def test_object_keys_reject_unsafe_ids(unsafe: str) -> None:
    keys = ObjectKeys("fit-check")
    with pytest.raises(ValueError):
        keys.garment_cutout(unsafe, "garment-1", 1)
