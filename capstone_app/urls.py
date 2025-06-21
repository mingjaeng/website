from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_redirect, name='home_redirect'),  # 루트 접속 시 index.html로 리다이렉트

    # 기업별 detail 페이지 (예시: /detail/apsi/, /detail/devsisters/)
    path('detail/<str:company>/', views.company_detail, name='company_detail'),

    # API: 예시로 크롤링된 주식정보 JSON 제공
    path('stock-info/', views.stock_info_api, name='stock_info'),
]