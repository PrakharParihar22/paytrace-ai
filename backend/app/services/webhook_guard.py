import threading


class WebhookEventGuard:
    """
    Tracks only SUCCESSFULLY processed webhook event IDs.

    Important:
    - Receipt alone does not make an event processed.
    - Failed processing is NOT marked complete, so a Razorpay retry can run.
    - A successfully processed duplicate can be acknowledged without
      repeating the merchant business action.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._processed = set()

    def is_processed(
        self,
        event_id: str | None,
    ) -> bool:
        if not event_id:
            return False

        with self._lock:
            return event_id in self._processed

    def mark_processed(
        self,
        event_id: str | None,
    ):
        if not event_id:
            return

        with self._lock:
            self._processed.add(event_id)


_LIVE_GUARD = WebhookEventGuard()


def is_webhook_processed(
    event_id: str | None,
) -> bool:
    return _LIVE_GUARD.is_processed(
        event_id
    )


def mark_webhook_processed(
    event_id: str | None,
):
    _LIVE_GUARD.mark_processed(
        event_id
    )
