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


def test_encrypt_decrypt_empty_inputs(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    user_id = "empty-user"

    assert crypto.encrypt_for_user(user_id, None) == ""
    assert crypto.decrypt_for_user(user_id, None) == ""


def test_ensure_user_key_warns_on_chmod_failure(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))

    def boom(*_args, **_kwargs):
        raise OSError("chmod unsupported")

    monkeypatch.setattr(crypto.os, "chmod", boom)

    caplog.set_level("WARNING")
    key = crypto.ensure_user_key("chmod-user")

    # Key is still generated even if chmod fails
    assert key
    assert "Failed to set permissions" in caplog.text
