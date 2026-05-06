from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView
from django.http import HttpResponse
from django.contrib.auth import get_user_model

def create_admin(request):
    User = get_user_model()
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        return HttpResponse("Admin account created! User: admin, Pass: admin123. PLEASE LOG IN AND THEN TELL ME TO REMOVE THIS ROUTE.")
    return HttpResponse("Admin account already exists.")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('graphql/', csrf_exempt(GraphQLView.as_view(graphiql=True))),
    path('create-admin/', create_admin),
]
