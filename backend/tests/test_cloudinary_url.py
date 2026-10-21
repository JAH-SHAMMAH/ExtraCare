from app.services.storage import _clean_cloudinary_url


def test_cleans_common_paste_mistakes():
    good = "cloudinary://123:abc@mycloud"
    assert _clean_cloudinary_url(good) == good
    assert _clean_cloudinary_url(f"CLOUDINARY_URL={good}") == good
    assert _clean_cloudinary_url(f' "{good}" ') == good
    assert _clean_cloudinary_url("cloudinary://<123>:<abc>@mycloud") == good
