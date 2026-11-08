import pytest

from swarm.retry import backoff_delay, call_with_retry, is_quota_error, is_retryable


class Http429(Exception):
    pass


def test_retryable_classification():
    assert is_retryable(Http429("Error code: 429 - rate limit"))
    assert is_retryable(TimeoutError("timed out"))
    assert is_retryable(ConnectionError("connection reset"))
    assert not is_retryable(ValueError("bad model id"))


def test_daily_quota_is_distinct():
    assert is_quota_error(RuntimeError("free-models-per-day limit reached"))
    assert is_quota_error(RuntimeError("Daily quota exceeded"))
    assert not is_quota_error(Http429("temporary 429"))


def test_backoff_grows_and_caps():
    delays = [backoff_delay(i, jitter=0) for i in (1, 2, 3, 4, 9)]
    assert delays[:4] == [1.0, 2.0, 4.0, 8.0]
    assert delays[4] == 8.0


def test_call_with_retry_recovers():
    calls = []
    sleeps = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise Http429("429")
        return "ok"

    assert call_with_retry(flaky, attempts=3, sleep=sleeps.append) == "ok"
    assert len(calls) == 3
    assert len(sleeps) == 2


def test_call_with_retry_does_not_retry_fatal_errors():
    calls = []

    def fatal():
        calls.append(1)
        raise ValueError("nope")

    with pytest.raises(ValueError):
        call_with_retry(fatal, attempts=3, sleep=lambda _: None)
    assert len(calls) == 1


def test_call_with_retry_raises_last_error():
    with pytest.raises(Http429):
        call_with_retry(lambda: (_ for _ in ()).throw(Http429("still 429")), attempts=2, sleep=lambda _: None)


def test_on_retry_hook_receives_attempt():
    seen = []
    with pytest.raises(Http429):
        call_with_retry(
            lambda: (_ for _ in ()).throw(Http429("429")),
            attempts=2,
            sleep=lambda _: None,
            on_retry=lambda n, e, d: seen.append((n, type(e).__name__, d)),
        )
    assert seen and seen[0][0] == 1 and seen[0][1] == "Http429"
