import json
import os

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")

_producer = None


async def _get_producer():
    global _producer
    if _producer is None:
        from aiokafka import AIOKafkaProducer
        _producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER)
        await _producer.start()
    return _producer


async def send_message_event(topic: str, payload: dict):
    try:
        producer = await _get_producer()
        await producer.send_and_wait(
            topic, json.dumps(payload).encode()
        )
    except Exception as exc:
        print(f"[kafka] send failed on {topic}: {exc}", flush=True)
