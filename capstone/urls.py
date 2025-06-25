from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('capstone_app.urls')),  # capstone_app의 URL을 사용
]