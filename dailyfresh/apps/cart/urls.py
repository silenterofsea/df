from django.urls import path
from . import views
from apps.cart.views import CartAddView, CartInfoView

app_name = 'cart'

urlpatterns = [
    path('add', CartAddView.as_view(), name='add'),
    path('', CartInfoView.as_view(), name='show')
]
