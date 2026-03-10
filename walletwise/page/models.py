from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError


class UserProfile(models.Model):
    SALARY_FREQ = [
        ('monthly', 'Monthly (1st of each month)'),
        ('semi',    'Semi-monthly (1st & 16th)'),
    ]

    user             = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    monthly_salary   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    salary_frequency = models.CharField(max_length=10, choices=SALARY_FREQ, default='monthly')
    currency         = models.CharField(max_length=5, default='₱')
    last_salary_date = models.DateField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — Profile"

    @property
    def salary_per_release(self):
        """Amount credited per pay release."""
        if self.salary_frequency == 'semi':
            return (self.monthly_salary / Decimal('2')).quantize(Decimal('0.01'))
        return self.monthly_salary

    def get_net_balance(self):
        """All-time income minus all-time expenses."""
        income = Transaction.objects.filter(
            user=self.user, type='income'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

        expenses = Transaction.objects.filter(
            user=self.user, type='expense'
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

        return income - expenses


class RecurringExpense(models.Model):
    """Fixed bill auto-deducted on a schedule."""
    FREQ_CHOICES = [
        ('monthly', 'Monthly (1st of month)'),
        ('semi',    'Semi-monthly (1st & 16th)'),
    ]
    EXPENSE_CATEGORIES = [
        'Food', 'Rent', 'Transport', 'Utilities', 'Health',
        'Entertainment', 'Shopping', 'Education', 'Other',
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recurring_expenses')
    name       = models.CharField(max_length=100)
    category   = models.CharField(max_length=50, default='Other')
    amount     = models.DecimalField(max_digits=12, decimal_places=2)
    frequency  = models.CharField(max_length=10, choices=FREQ_CHOICES, default='monthly')
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.user.username} | {self.name} | ₱{self.amount}"

    @property
    def monthly_cost(self):
        return self.amount * 2 if self.frequency == 'semi' else self.amount


class AutoSavingsPlan(models.Model):
    """Automatic deduction that moves money into a SavingsGoal."""
    FREQ_CHOICES = [
        ('daily',   'Daily'),
        ('semi',    'Semi-monthly (1st & 16th)'),
        ('monthly', 'Monthly (1st of month)'),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auto_savings')
    goal       = models.ForeignKey('SavingsGoal', on_delete=models.CASCADE, related_name='auto_plans')
    amount     = models.DecimalField(max_digits=12, decimal_places=2)
    frequency  = models.CharField(max_length=10, choices=FREQ_CHOICES, default='monthly')
    is_active  = models.BooleanField(default=True)
    last_run   = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} | {self.goal.name} | ₱{self.amount}/{self.frequency}"

    @property
    def monthly_cost(self):
        import calendar
        if self.frequency == 'daily':
            today = date.today()
            days = calendar.monthrange(today.year, today.month)[1]
            return (self.amount * days).quantize(Decimal('0.01'))
        elif self.frequency == 'semi':
            return (self.amount * 2).quantize(Decimal('0.01'))
        return self.amount


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
    auto_tag    = models.CharField(max_length=30, blank=True,
                                   help_text='Marks auto-generated entries to prevent duplicates')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.user.username} | {self.type} | {self.category} | {self.amount}"

    def clean(self):
        """Prevent expenses when balance is insufficient. Skip check for auto entries."""
        if self.type == 'expense' and not self.auto_tag:
            current_balance = self.user.profile.get_net_balance()
            # If editing, add back the old amount so we compare fairly
            if self.pk:
                try:
                    old = Transaction.objects.get(pk=self.pk)
                    if old.type == 'expense':
                        current_balance += old.amount
                except Transaction.DoesNotExist:
                    pass
            if current_balance < self.amount:
                raise ValidationError(
                    f"Insufficient balance. Available: ₱{current_balance:,.2f}, "
                    f"Attempted: ₱{self.amount:,.2f}"
                )

    def save(self, *args, **kwargs):
        # skip=True is set by the scheduler to bypass balance check on auto entries
        skip_validation = kwargs.pop('skip_validation', False)
        if not skip_validation:
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

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='savings_goals')
    name       = models.CharField(max_length=100)
    category   = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='Emergency Fund')
    target     = models.DecimalField(max_digits=12, decimal_places=2)
    current    = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

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
    goal       = models.ForeignKey(SavingsGoal, on_delete=models.CASCADE, related_name='deposits')
    amount     = models.DecimalField(max_digits=12, decimal_places=2)
    note       = models.CharField(max_length=255, blank=True)
    date       = models.DateField(default=timezone.now)
    is_auto    = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.goal.name} | +{self.amount}"

    def clean(self):
        """Validate deposit is possible."""
        if not self.goal_id:
            return
        # Skip balance check for auto deposits (handled by scheduler)
        if not self.is_auto:
            balance = self.goal.user.profile.get_net_balance()
            if balance <= 0:
                raise ValidationError(
                    "Cannot deposit to savings when your net balance is zero or negative."
                )
        # Never exceed target
        if self.goal.current + self.amount > self.goal.target:
            raise ValidationError(
                f"Deposit exceeds remaining target. "
                f"Remaining: ₱{self.goal.remaining:,.2f}"
            )

    def save(self, *args, **kwargs):
        if self.goal_id and not self.is_auto:
            self.full_clean()
        super().save(*args, **kwargs)
        # Update goal progress
        if self.goal_id:
            self.goal.current = min(self.goal.target, self.goal.current + self.amount)
            self.goal.save(update_fields=['current'])


class Budget(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='budgets')
    category   = models.CharField(max_length=50)
    limit      = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'category']
        ordering = ['category']

    def __str__(self):
        return f"{self.user.username} | {self.category} | {self.limit}"