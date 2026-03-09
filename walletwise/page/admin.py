from django.contrib import admin
from .models import UserProfile, Transaction, SavingsGoal, SavingsDeposit, Budget

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'monthly_salary', 'created_at']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'type', 'category', 'amount', 'date', 'description']
    list_filter   = ['type', 'category']
    search_fields = ['user__username', 'description', 'category']

@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'category', 'target', 'current']

@admin.register(SavingsDeposit)
class SavingsDepositAdmin(admin.ModelAdmin):
    list_display = ['goal', 'amount', 'date']

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'limit']