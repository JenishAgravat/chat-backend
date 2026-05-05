from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from graphql_jwt.utils import jwt_decode
from django.conf import settings

User = get_user_model()

@database_sync_to_async
def get_user(token):
    try:
        # Use graphql_jwt's own decoder for consistency
        payload = jwt_decode(token)
        user = User.objects.get(username=payload.get('username'))
        return user
    except Exception as e:
        print(f"WebSocket auth error: {e}")
        return AnonymousUser()

class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = None
        for param in query_string.split("&"):
            if param.startswith("token="):
                token = param.split("=")[1]
        
        if token:
            scope['user'] = await get_user(token)
        else:
            scope['user'] = AnonymousUser()
        
        return await self.inner(scope, receive, send)
