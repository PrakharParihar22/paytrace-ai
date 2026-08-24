from app.services.event_service import get_events


def build_timeline(order_id):

    events = get_events(order_id)

    timeline = []

    for index, event in enumerate(
        events,
        start=1
    ):

        timeline.append({
            "sequence": index,
            "timestamp": event["created_at"],
            "source": event["source"],
            "type": event["event_type"],
            "status": event["status"],
            "message": event["message"],
            "payment_id": event["payment_id"],
            "metadata": event["metadata"]
        })

    return {
        "order_id": order_id,
        "event_count": len(timeline),
        "timeline": timeline
    }