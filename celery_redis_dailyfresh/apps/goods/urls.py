from django.urls import path
from . import views

app_name = 'goods'

urlpatterns = [
    path('index/', views.index, name='index')
]
