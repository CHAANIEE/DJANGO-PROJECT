from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile, Transaction, SavingsGoal, SavingsDeposit, Budget
from .models import SavingsDeposit, SavingsGoal # Ensure this is correct


INCOME_CATEGORIES = ['Salary','Freelance','Bonus','Investment','Side Hustle','Gift','Other Income']
EXPENSE_CATEGORIES = ['Food','Rent','Transport','Utilities','Health','Entertainment','Shopping','Education','Other']
SAVING_CATEGORIES  = ['Emergency Fund','Investment','Retirement','Travel','House','Car','Education','Other']

W = {'class': 'form-control'}
S = {'class': 'form-select'}


class RegisterForm(UserCreationForm):
    first_name     = forms.CharField(max_length=50,  widget=forms.TextInput(attrs={**W, 'placeholder': 'First Name'}))
    last_name      = forms.CharField(max_length=50,  widget=forms.TextInput(attrs={**W, 'placeholder': 'Last Name'}))
    email          = forms.EmailField(widget=forms.EmailInput(attrs={**W, 'placeholder': 'Email'}))
    monthly_salary = forms.DecimalField(min_value=0, widget=forms.NumberInput(attrs={**W, 'placeholder': '0.00', 'step': '0.01'}))

    class Meta:
        model  = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {'username': forms.TextInput(attrs={**W, 'placeholder': 'Username'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={**W, 'placeholder': 'Password'})
        self.fields['password2'].widget = forms.PasswordInput(attrs={**W, 'placeholder': 'Confirm Password'})


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs=W))
    last_name  = forms.CharField(max_length=50, widget=forms.TextInput(attrs=W))

    class Meta:
        model   = UserProfile
        fields  = ['monthly_salary']
        widgets = {'monthly_salary': forms.NumberInput(attrs={**W, 'step': '0.01', 'min': '0'})}


class TransactionForm(forms.ModelForm):
    class Meta:
        model   = Transaction
        fields  = ['type', 'category', 'amount', 'description', 'date']
        widgets = {
            'type':        forms.Select(attrs=S),
            'category':    forms.Select(attrs=S),
            'amount':      forms.NumberInput(attrs={**W, 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'description': forms.TextInput(attrs={**W, 'placeholder': 'Optional note…'}),
            'date':        forms.DateInput(attrs={**W, 'type': 'date'}),
        }

    def __init__(self, *args, txn_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        if txn_type == 'income':
            self.fields['category'].widget = forms.Select(
                attrs=S, choices=[('', '— Select —')] + [(c, c) for c in INCOME_CATEGORIES])
            self.fields['type'].initial = 'income'
        elif txn_type == 'expense':
            self.fields['category'].widget = forms.Select(
                attrs=S, choices=[('', '— Select —')] + [(c, c) for c in EXPENSE_CATEGORIES])
            self.fields['type'].initial = 'expense'
        else:
            all_cats = [('', '— Select —')] + [(c, c) for c in INCOME_CATEGORIES + EXPENSE_CATEGORIES]
            self.fields['category'].widget = forms.Select(attrs=S, choices=all_cats)


class SavingsGoalForm(forms.ModelForm):
    class Meta:
        model   = SavingsGoal
        fields  = ['name', 'category', 'target', 'current']
        widgets = {
            'name':     forms.TextInput(attrs={**W, 'placeholder': 'e.g. Emergency Fund, Dream Vacation…'}),
            'category': forms.Select(attrs=S),
            'target':   forms.NumberInput(attrs={**W, 'step': '0.01', 'min': '1', 'placeholder': '0.00'}),
            'current':  forms.NumberInput(attrs={**W, 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        }


class SavingsDepositForm(forms.ModelForm):
    class Meta:
        model   = SavingsDeposit
        fields  = ['amount', 'note', 'date']
        widgets = {
            'amount': forms.NumberInput(attrs={**W, 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'note':   forms.TextInput(attrs={**W, 'placeholder': 'Optional note…'}),
            'date':   forms.DateInput(attrs={**W, 'type': 'date'}),
        }


class BudgetForm(forms.ModelForm):
    class Meta:
        model   = Budget
        fields  = ['category', 'limit']
        widgets = {
            'category': forms.Select(attrs=S, choices=[('', '— Select —')] + [(c, c) for c in EXPENSE_CATEGORIES]),
            'limit':    forms.NumberInput(attrs={**W, 'step': '0.01', 'min': '1', 'placeholder': '0.00'}),
        }