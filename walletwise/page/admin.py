from django.contrib import admin
from .models import (UserProfile, Transaction, SavingsGoal, SavingsDeposit,
                     Budget, RecurringExpense, AutoSavingsPlan)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'monthly_salary', 'salary_frequency', 'last_salary_date']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'type', 'category', 'amount', 'date', 'auto_tag']
    list_filter   = ['type', 'category', 'auto_tag']
    search_fields = ['user__username', 'description', 'category']

@admin.register(RecurringExpense)
class RecurringExpenseAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'category', 'amount', 'frequency', 'is_active']
    list_filter  = ['is_active', 'frequency']

@admin.register(AutoSavingsPlan)
class AutoSavingsPlanAdmin(admin.ModelAdmin):
    list_display = ['user', 'goal', 'amount', 'frequency', 'is_active', 'last_run']
    list_filter  = ['is_active', 'frequency']

@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ['user', 'name', 'category', 'target', 'current']

@admin.register(SavingsDeposit)
class SavingsDepositAdmin(admin.ModelAdmin):
    list_display = ['goal', 'amount', 'date', 'is_auto']

@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ['user', 'category', 'limit']