import datetime

from hews.client import HNClient


def test_algolia_hit_fallback_time_uses_injected_clock():
    fixed_time = datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
    client = HNClient(clock=lambda: fixed_time)

    story = client._algolia_hit_to_story(
        {
            "objectID": "123",
            "title": "Story without Algolia timestamp",
            "author": "tester",
        }
    )

    assert story is not None
    assert story.time == fixed_time


def test_algolia_hit_with_epoch_timestamp_does_not_call_injected_clock():
    calls = 0

    def fake_clock():
        nonlocal calls
        calls += 1
        return datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)

    client = HNClient(clock=fake_clock)

    story = client._algolia_hit_to_story(
        {
            "objectID": "123",
            "title": "Story with epoch timestamp",
            "author": "tester",
            "created_at_i": 0,
        }
    )

    assert story is not None
    assert story.time == datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    assert calls == 0


def test_algolia_hit_missing_timestamp_calls_injected_clock():
    calls = 0
    fixed_time = datetime.datetime(2024, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)

    def fake_clock():
        nonlocal calls
        calls += 1
        return fixed_time

    client = HNClient(clock=fake_clock)

    story = client._algolia_hit_to_story(
        {
            "objectID": "123",
            "title": "Story without timestamp",
            "author": "tester",
        }
    )

    assert story is not None
    assert story.time == fixed_time
    assert calls == 1
