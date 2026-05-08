import json
import threading
from kafka import KafkaProducer, KafkaConsumer
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.conf import settings

import os

KAFKA_BROKER = os.environ.get('KAFKA_BROKER')
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'chat_messages')

_producer = None
_producer_lock = threading.Lock()

def get_producer():
    global _producer
    if not KAFKA_BROKER:
        return None
    
    if _producer is not None:
        return _producer

    with _producer_lock:
        if _producer is not None:
            return _producer
            
        try:
            _producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BROKER],
                value_serializer=lambda x: json.dumps(x).encode('utf-8'),
                max_block_ms=500, # Reduced from 1000 to minimize lag
                request_timeout_ms=500,
                api_version_auto_timeout_ms=500
            )
            return _producer
        except Exception as e:
            print(f"Kafka Producer init failed: {e}")
            return None

def send_message_event(sender_id, receiver_id, content, reply_to_id=None):
    """Send a new chat message. Tries Kafka first, falls back to sync."""
    data = {
        'sender_id': sender_id,
        'receiver_id': receiver_id,
        'content': content,
        'reply_to_id': reply_to_id,
    }
    
    current_producer = get_producer()
    if current_producer:
        try:
            future = current_producer.send(KAFKA_TOPIC, value=data)
            future.get(timeout=0.5)
        except Exception as e:
            print(f"Kafka delivery failed, falling back to sync: {e}")
            handle_message_sync(data)
    else:
        handle_message_sync(data)

def handle_message_sync(data):
    """Save message to DB and broadcast via WebSocket to both users."""
    from .models import Message, User

    sender = User.objects.get(id=data['sender_id'])
    receiver = User.objects.get(id=data['receiver_id'])

    # Build create kwargs
    create_kwargs = {
        'sender': sender,
        'receiver': receiver,
        'content': data['content'],
    }

    # Handle reply_to
    reply_to_id = data.get('reply_to_id')
    reply_to_content = None
    if reply_to_id:
        try:
            parent = Message.objects.get(id=reply_to_id)
            create_kwargs['reply_to'] = parent
            reply_to_content = parent.content[:50]
        except Message.DoesNotExist:
            pass

    msg = Message.objects.create(**create_kwargs)

    channel_layer = get_channel_layer()

    # Build the event payload
    event_data = {
        "type": "chat_message",
        "message_id": msg.id,
        "sender_id": sender.id,
        "receiver_id": receiver.id,
        "content": msg.content,
        "timestamp": msg.timestamp.isoformat(),
        "reaction": None,
        "reply_to_id": reply_to_id,
        "reply_to_content": reply_to_content,
    }

    # Send to receiver
    async_to_sync(channel_layer.group_send)(
        f"user_{receiver.id}", event_data
    )

    # Send notification to receiver
    async_to_sync(channel_layer.group_send)(
        f"user_{receiver.id}",
        {
            "type": "notification",
            "message": f"New message from {sender.username}"
        }
    )

    # Send back to sender (so their UI updates too)
    async_to_sync(channel_layer.group_send)(
        f"user_{sender.id}", event_data
    )

def start_kafka_consumer():
    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=[KAFKA_BROKER],
            auto_offset_reset='latest',
            enable_auto_commit=True,
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        for message in consumer:
            handle_message_sync(message.value)
    except Exception:
        pass

def init_consumer():
    if not KAFKA_BROKER:
        print("Kafka not configured, skipping consumer initialization.")
        return
    t = threading.Thread(target=start_kafka_consumer, daemon=True)
    t.start()
