from pathlib import Path

from app.tools import crypto
from app.config import settings


def test_encrypt_decrypt_roundtrip(monkeypatch, tmp_path):
    # Point keys directory to a temp path
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    user_id = "test-user-crypto"
    plaintext = "Taking 1 tablet in the morning"

    token = crypto.encrypt_for_user(user_id, plaintext)
    assert token and token != plaintext

    recovered = crypto.decrypt_for_user(user_id, token)
    assert recovered == plaintext

    # Key file created under data_dir/keys/<user_id>.key
    keys_dir = Path(settings.data_dir) / "keys"
    assert (keys_dir / f"{user_id}.key").exists()
