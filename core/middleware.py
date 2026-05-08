from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from graphql_jwt.utils import jwt_decode
from django.conf import settings
import traceback

User = get_user_model()

@database_sync_to_async
def get_user(token):
    try:
        payload = jwt_decode(token)
        username = payload.get('username')
        user = User.objects.get(username=username)
        return user
    except Exception as e:
        return AnonymousUser()

class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = None
        
        # More robust token extraction
        if "token=" in query_string:
            try:
                token = query_string.split("token=")[1].split("&")[0]
            except Exception:
                pass
        
        if token:
            scope['user'] = await get_user(token)
        else:
            print("No token found in query string")
            scope['user'] = AnonymousUser()
        
        return await self.inner(scope, receive, send)
