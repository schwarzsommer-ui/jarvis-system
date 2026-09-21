def test_live_publisher_emits_typed_event():
    from backend.live_publisher import LiveEventPublisher
    publisher = LiveEventPublisher()
    event = publisher.publish("test.event", {"ok": True})
    assert event["type"] == "test.event"
    assert event["payload"]["ok"] is True
