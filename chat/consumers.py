import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.user_group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.channel_layer.group_add("global_presence", self.channel_name)
        
        await self.set_online_status(True)
        await self.channel_layer.group_send("global_presence", {
            "type": "user_status",
            "user_id": self.user.id,
            "is_online": True
        })
        
        await self.accept()

    async def disconnect(self, close_code):
        if not hasattr(self, "user") or self.user.is_anonymous:
            return
            
        await self.set_online_status(False)
        await self.channel_layer.group_send("global_presence", {
            "type": "user_status",
            "user_id": self.user.id,
            "is_online": False
        })
        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)
        await self.channel_layer.group_discard("global_presence", self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'chat_message':
            receiver_id = data['receiver_id']
            content = data['content']
            reply_to_id = data.get('reply_to', None)
            
            await self.produce_message(self.user.id, receiver_id, content, reply_to_id)

        elif message_type == 'add_reaction':
            message_id = data['message_id']
            reaction = data['reaction']
            await self.save_reaction(message_id, reaction)

    @database_sync_to_async
    def set_online_status(self, status):
        self.user.is_online = status
        self.user.save(update_fields=['is_online'])

    @database_sync_to_async
    def produce_message(self, sender_id, receiver_id, content, reply_to_id=None):
        from .kafka_utils import send_message_event
        send_message_event(sender_id, receiver_id, content, reply_to_id=reply_to_id)

    @database_sync_to_async
    def save_reaction(self, message_id, reaction):
        from .models import Message
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        try:
            msg = Message.objects.get(id=message_id)
            msg.reaction = reaction
            msg.save(update_fields=['reaction'])

            channel_layer = get_channel_layer()
            # Broadcast reaction update to both sender and receiver
            for uid in [msg.sender.id, msg.receiver.id]:
                async_to_sync(channel_layer.group_send)(
                    f"user_{uid}",
                    {
                        "type": "reaction_update",
                        "message_id": msg.id,
                        "reaction": reaction,
                    }
                )
        except Message.DoesNotExist:
            pass

    async def user_status(self, event):
        await self.send(text_data=json.dumps(event))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
        
    async def notification(self, event):
        await self.send(text_data=json.dumps(event))

    async def reaction_update(self, event):
        await self.send(text_data=json.dumps(event))
