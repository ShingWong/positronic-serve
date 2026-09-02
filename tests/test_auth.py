# tests/test_auth.py
import pytest
from positronic_serve.auth import LocalKeyManager, SingleKeyManager, build_key_manager


def test_local_manager_accepts_any_or_no_token():
    m = LocalKeyManager()
    assert m.validate(None) is True
    assert m.validate("anything") is True


def test_single_manager_requires_exact_key():
    m = SingleKeyManager("sekret")
    assert m.validate("sekret") is True
    assert m.validate("wrong") is False
    assert m.validate(None) is False


def test_build_local_default():
    assert isinstance(build_key_manager({"manager": "local"}), LocalKeyManager)


def test_build_single_uses_key():
    m = build_key_manager({"manager": "single", "key": "abc"})
    assert m.validate("abc") is True and m.validate("nope") is False


def test_build_unknown_manager_raises():
    with pytest.raises(ValueError):
        build_key_manager({"manager": "google"})