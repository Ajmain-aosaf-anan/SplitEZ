'''core/urls.py'''

from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('create_group/', views.create_group, name='create_group'),
    path('group/<int:group_id>/', views.group_detail, name='group_detail'),
    path('add_expense/<int:group_id>/', views.add_expense, name='add_expense'),
    path('join_group/', views.join_group, name='join_group'),
    path('group_qr/<int:group_id>/', views.group_qr, name='group_qr'),
    path('join_group_by_id/<int:group_id>/', views.join_group_by_id, name='join_group_by_id'),
    path('pay_debt/<int:debt_id>/', views.pay_debt, name='pay_debt'),
]