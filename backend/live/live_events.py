from backend.live_publisher import LiveEventPublisher

publisher = LiveEventPublisher()

def send_log(message: str): return publisher.publish("logs", {"message": message})
def send_agent_status(status: dict): return publisher.publish("agent-status", status)
def send_executor_queue_state(state: dict): return publisher.publish("queue", state)
def send_memory_event(event: dict): return publisher.publish("memory", event)
