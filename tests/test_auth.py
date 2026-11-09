
from app.auth import hash_token, mint_token, verify_token


def test_mint_token_is_128_bit():
    token = mint_token()
    assert len(token) == 32
    assert all(c in "0123456789abcdef" for c in token)


def test_mint_token_is_unique():
    tokens = {mint_token() for _ in range(100)}
    assert len(tokens) == 100


def test_hash_token_is_deterministic():
    assert hash_token("abc123") == hash_token("abc123")


def test_hash_token_is_one_way():
    digest = hash_token("abc123")
    assert digest != "abc123"
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_verify_token_valid():
    token = mint_token()
    assert verify_token(token, hash_token(token)) is True


def test_verify_token_invalid():
    token = mint_token()
    wrong_token = mint_token()
    assert verify_token(wrong_token, hash_token(token)) is False


def test_token_is_never_logged(caplog):
    import logging

    with caplog.at_level(logging.DEBUG):
        token = mint_token()
        digest = hash_token(token)
        verify_token(token, digest)

    assert token not in caplog.text
    assert digest not in caplog.text
