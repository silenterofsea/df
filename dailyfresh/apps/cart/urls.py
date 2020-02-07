from django.urls import path
from . import views
from apps.cart.views import CartAddView, CartInfoView, CartUpdateView

app_name = 'cart'

urlpatterns = [
    path('add', CartAddView.as_view(), name='add'),
    path('update', CartUpdateView.as_view(), name='update'),
    path('', CartInfoView.as_view(), name='show')
]
