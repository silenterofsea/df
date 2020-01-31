from django.urls import path
from apps.goods.views import IndexView

app_name = 'goods'

urlpatterns = [
    path('', IndexView.as_view(), name='index')
]
