from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('detail/<str:company_name>/', views.company_detail, name='company_detail'),
    path('stock-info/', views.stock_info_api, name='stock_info'),
]
