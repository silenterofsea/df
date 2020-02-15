from django.urls import path
from . import views
from apps.order.views import OrderPlaceView, OrderCommitView, OrderPayView

app_name = 'order'

urlpatterns = [
    path('place', OrderPlaceView.as_view(), name='place'),
    path('commit', OrderCommitView.as_view(), name='commit'),
    path('pay', OrderPayView.as_view(), name='pay')
]
