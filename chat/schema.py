import graphene
from graphene_django import DjangoObjectType
from django.contrib.auth import get_user_model
import graphql_jwt
from graphql_jwt.shortcuts import get_token, create_refresh_token
from .models import Message
from graphql_jwt.decorators import login_required
from django.db.models import Q

User = get_user_model()

class UserType(DjangoObjectType):
    class Meta:
        model = User
        fields = ("id", "username", "email", "is_online")

class MessageType(DjangoObjectType):
    class Meta:
        model = Message
        fields = ("id", "sender", "receiver", "content", "timestamp", "is_read", "reaction", "reply_to")

# ──────────────────────────────────────────────
#  QUERIES
# ──────────────────────────────────────────────
class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    users = graphene.List(UserType)
    messages = graphene.List(MessageType, user_id=graphene.Int())

    @login_required
    def resolve_me(self, info):
        return info.context.user

    @login_required
    def resolve_users(self, info):
        return User.objects.exclude(id=info.context.user.id)

    @login_required
    def resolve_messages(self, info, user_id):
        user = info.context.user
        return Message.objects.filter(
            Q(sender=user, receiver_id=user_id) | Q(sender_id=user_id, receiver=user)
        ).select_related('reply_to').order_by('timestamp')

# ──────────────────────────────────────────────
#  MUTATIONS
# ──────────────────────────────────────────────
class CreateUser(graphene.Mutation):
    user = graphene.Field(UserType)
    token = graphene.String()
    refresh_token = graphene.String()

    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)
        email = graphene.String(required=True)

    def mutate(self, info, username, password, email):
        if User.objects.filter(username=username).exists():
            raise Exception("Username already exists")
        user = User(username=username, email=email)
        user.set_password(password)
        user.save()
        token = get_token(user)
        refresh_token = create_refresh_token(user)
        return CreateUser(user=user, token=token, refresh_token=refresh_token)

class AddReaction(graphene.Mutation):
    message = graphene.Field(MessageType)

    class Arguments:
        message_id = graphene.ID(required=True)
        reaction = graphene.String(required=True)

    @login_required
    def mutate(self, info, message_id, reaction):
        """Toggle reaction on a message — just saves to DB. 
        Real-time broadcast is handled by the WebSocket consumer."""
        try:
            msg = Message.objects.get(id=message_id)
            # Toggle: if same reaction, remove it; otherwise set it
            if msg.reaction == reaction:
                msg.reaction = None
            else:
                msg.reaction = reaction
            msg.save(update_fields=['reaction'])
            return AddReaction(message=msg)
        except Message.DoesNotExist:
            raise Exception("Message not found")

class Mutation(graphene.ObjectType):
    create_user = CreateUser.Field()
    token_auth = graphql_jwt.ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()
    add_reaction = AddReaction.Field()
