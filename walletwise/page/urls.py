from django.urls import path
from . import views

urlpatterns = [
    path('',                            views.dashboard,          name='dashboard'),
    path('transactions/',               views.transactions,       name='transactions'),
    path('transactions/add/',           views.add_transaction,    name='add_transaction'),
    path('transactions/<int:pk>/edit/', views.edit_transaction,   name='edit_transaction'),
    path('transactions/<int:pk>/delete/', views.delete_transaction, name='delete_transaction'),
    path('savings/',                    views.savings,            name='savings'),
    path('savings/add/',                views.add_savings_goal,   name='add_savings_goal'),
    path('savings/<int:pk>/edit/',      views.edit_savings_goal,  name='edit_savings_goal'),
    path('savings/<int:pk>/delete/',    views.delete_savings_goal,name='delete_savings_goal'),
    path('savings/<int:pk>/deposit/',   views.deposit_savings,    name='deposit_savings'),
    path('budget/',                     views.budget,             name='budget'),
    path('budget/add/',                 views.add_budget,         name='add_budget'),
    path('budget/<int:pk>/edit/',       views.edit_budget,        name='edit_budget'),
    path('budget/<int:pk>/delete/',     views.delete_budget,      name='delete_budget'),
    path('analytics/',                  views.analytics,          name='analytics'),
    path('profile/',                    views.profile,            name='profile'),
]