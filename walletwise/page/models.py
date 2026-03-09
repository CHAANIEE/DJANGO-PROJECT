from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction

class UserProfile(models.Model):
    user         = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    monthly_salary = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency     = models.CharField(max_length=5, default='₱')
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — Profile"
    
    def get_net_balance(self):
        """Calculates: Total Income - Total Expenses for the user"""
        income = Transaction.objects.filter(user=self.user, type='income').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        expenses = Transaction.objects.filter(user=self.user, type='expense').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0')
        
        return income - expenses

class Transaction(models.Model):
    TYPE_CHOICES = [('income', 'Income'), ('expense', 'Expense')]

    INCOME_CATEGORIES = [
        'Salary', 'Freelance', 'Bonus', 'Investment',
        'Side Hustle', 'Gift', 'Other Income',
    ]
    EXPENSE_CATEGORIES = [
        'Food', 'Rent', 'Transport', 'Utilities', 'Health',
        'Entertainment', 'Shopping', 'Education', 'Savings Deposit', 'Other',
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    type        = models.CharField(max_length=10, choices=TYPE_CHOICES)
    category    = models.CharField(max_length=50)
    amount      = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    date        = models.DateField(default=timezone.now)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.user.username} | {self.type} | {self.category} | {self.amount}"
    
    def clean(self):
        """Validate transaction logic before saving"""
        if self.type == 'expense':
            # Calculate current balance BEFORE this new expense
            # We exclude the current instance if it's being edited
            current_balance = self.user.profile.get_net_balance()
            
            # If editing, add back the old amount to get the "real" current balance
            if self.pk:
                old_txn = Transaction.objects.get(pk=self.pk)
                if old_txn.type == 'expense':
                    current_balance += old_txn.amount
            
            if current_balance < self.amount:
                raise ValidationError(f"Insufficient funds. Current balance: ₱{current_balance:,.2f}, Attempted: ₱{self.amount:,.2f}")

    def save(self, *args, **kwargs):
        # Run validation
        self.full_clean()
        super().save(*args, **kwargs)

class SavingsGoal(models.Model):
    CATEGORY_CHOICES = [
        ('Emergency Fund', 'Emergency Fund'),
        ('Investment',     'Investment'),
        ('Retirement',     'Retirement'),
        ('Travel',         'Travel'),
        ('House',          'House'),
        ('Car',            'Car'),
        ('Education',      'Education'),
        ('Other',          'Other'),
    ]

    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_goals')
    name        = models.CharField(max_length=100)
    category    = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Emergency Fund')
    target      = models.DecimalField(max_digits=12, decimal_places=2)
    current     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    @property
    def percent(self):
        if self.target > 0:
            return min(100, int((self.current / self.target) * 100))
        return 0

    @property
    def remaining(self):
        return max(Decimal('0'), self.target - self.current)

    @property
    def is_complete(self):
        return self.current >= self.target

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} | {self.name}"


class SavingsDeposit(models.Model):
    goal = models.ForeignKey(SavingsGoal, on_delete=models.CASCADE, related_name='deposits')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.goal.name} | +{self.amount}"

    def clean(self):
        """Ensure user has positive net balance before depositing"""
        # Only validate if goal is actually set
        if self.goal_id:
            # Check if user has positive net balance
            if self.goal.user.profile.get_net_balance() <= 0:
                raise ValidationError("Cannot deposit to savings when net balance is zero or negative.")
            
            # Check if deposit exceeds target
            if self.goal.current + self.amount > self.goal.target:
                raise ValidationError("Deposit amount exceeds the remaining target.")

    def save(self, *args, **kwargs):
        # Only run validation if goal is set
        if self.goal_id:
            self.full_clean()
        
        super().save(*args, **kwargs)
        
        # Update the goal's current amount (only if goal is set)
        if self.goal_id:
            self.goal.current = min(self.goal.target, self.goal.current + self.amount)
            self.goal.save()
        
class Budget(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category    = models.CharField(max_length=50)
    limit       = models.DecimalField(max_digits=12, decimal_places=2)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'category']
        ordering = ['category']

    def __str__(self):
        return f"{self.user.username} | {self.category} | {self.limit}"