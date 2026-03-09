from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import json
from django.core.exceptions import ValidationError  # ← ADD THIS LINE

from .models import UserProfile, Transaction, SavingsGoal, SavingsDeposit, Budget
from .forms import (RegisterForm, ProfileForm, TransactionForm,
                    SavingsGoalForm, SavingsDepositForm, BudgetForm)

from .models import UserProfile, Transaction, SavingsGoal, SavingsDeposit, Budget
from .forms import (RegisterForm, ProfileForm, TransactionForm,
                    SavingsGoalForm, SavingsDepositForm, BudgetForm)

INCOME_CATEGORIES  = ['Salary','Freelance','Bonus','Investment','Side Hustle','Gift','Other Income']
EXPENSE_CATEGORIES = ['Food','Rent','Transport','Utilities','Health','Entertainment','Shopping','Education','Other']

CAT_COLORS = {
    'Salary':'#22c55e','Freelance':'#3b82f6','Bonus':'#f59e0b','Investment':'#8b5cf6',
    'Side Hustle':'#06b6d4','Gift':'#ec4899','Other Income':'#10b981',
    'Food':'#ef4444','Rent':'#f97316','Transport':'#eab308','Utilities':'#84cc16',
    'Health':'#14b8a6','Entertainment':'#a855f7','Shopping':'#ec4899',
    'Education':'#6366f1','Other':'#94a3b8',
    'Emergency Fund':'#22c55e','Retirement':'#3b82f6','Travel':'#f59e0b',
    'House':'#8b5cf6','Car':'#06b6d4',
}

GOAL_COLORS = {
    'Emergency Fund':'#22c55e','Investment':'#3b82f6','Retirement':'#6366f1',
    'Travel':'#f59e0b','House':'#8b5cf6','Car':'#06b6d4','Education':'#ec4899','Other':'#94a3b8',
}


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _month_range(year, month):
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end


# ── Auth ──────────────────────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.first_name = form.cleaned_data['first_name']
            user.last_name  = form.cleaned_data['last_name']
            user.email      = form.cleaned_data['email']
            user.save()
            UserProfile.objects.create(
                user=user,
                monthly_salary=form.cleaned_data['monthly_salary']
            )
            login(request, user)
            messages.success(request, f'Welcome to WalletWise, {user.first_name}!')
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'salary/register.html', {'form': form})


# ── Dashboard ─────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    profile = _get_or_create_profile(request.user)
    today   = date.today()
    start, end = _month_range(today.year, today.month)

    month_txns = Transaction.objects.filter(
        user=request.user, date__gte=start, date__lte=end)

    total_income  = month_txns.filter(type='income').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    total_expense = month_txns.filter(type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    net_balance   = total_income - total_expense

    # Savings totals
    total_saved = SavingsGoal.objects.filter(user=request.user).aggregate(s=Sum('current'))['s'] or Decimal('0')

    # Monthly trend — last 6 months
    trend = []
    for i in range(5, -1, -1):
        ref = date(today.year, today.month, 1) - timedelta(days=i * 30)
        ms, me = _month_range(ref.year, ref.month)
        txns = Transaction.objects.filter(user=request.user, date__gte=ms, date__lte=me)
        inc  = txns.filter(type='income').aggregate(s=Sum('amount'))['s']  or Decimal('0')
        exp  = txns.filter(type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')
        trend.append({
            'month':   ref.strftime('%b %Y'),
            'income':  float(inc),
            'expense': float(exp),
        })

    # Expense breakdown by category (this month)
    exp_cats = []
    for cat in EXPENSE_CATEGORIES:
        val = month_txns.filter(type='expense', category=cat).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        if val > 0:
            exp_cats.append({'name': cat, 'value': float(val), 'color': CAT_COLORS.get(cat, '#64748b')})

    # Budget usage
    budgets = Budget.objects.filter(user=request.user)
    budget_data = []
    for b in budgets:
        spent = month_txns.filter(type='expense', category=b.category).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        pct   = min(100, int((spent / b.limit) * 100)) if b.limit > 0 else 0
        budget_data.append({
            'id': b.id, 'category': b.category,
            'limit': b.limit, 'spent': spent,
            'remaining': max(Decimal('0'), b.limit - spent),
            'pct': pct, 'over': spent > b.limit,
            'color': CAT_COLORS.get(b.category, '#64748b'),
        })

    # Savings goals
    goals = SavingsGoal.objects.filter(user=request.user)
    goal_data = [{'id': g.id, 'name': g.name, 'category': g.category,
                  'target': g.target, 'current': g.current,
                  'percent': g.percent, 'remaining': g.remaining,
                  'is_complete': g.is_complete,
                  'color': GOAL_COLORS.get(g.category, '#38bdf8')} for g in goals]

    # Recent transactions
    recent = Transaction.objects.filter(user=request.user).select_related()[:8]

    context = {
        'profile':       profile,
        'total_income':  total_income,
        'total_expense': total_expense,
        'net_balance':   net_balance,
        'total_saved':   total_saved,
        'trend_json':    json.dumps(trend),
        'exp_cats_json': json.dumps(exp_cats),
        'budget_data':   budget_data,
        'goal_data':     goal_data,
        'recent':        recent,
        'current_month': today.strftime('%B %Y'),
        'greeting':      _greeting(),
    }
    return render(request, 'salary/dashboard.html', context)


def _greeting():
    h = timezone.localtime().hour
    return 'Good Morning' if h < 12 else ('Good Afternoon' if h < 17 else 'Good Evening')


# ── Transactions ──────────────────────────────────────────────────────

@login_required
def transactions(request):
    txn_type = request.GET.get('type', 'all')
    q        = request.GET.get('q', '')
    month    = request.GET.get('month', '')

    qs = Transaction.objects.filter(user=request.user)
    if txn_type in ('income', 'expense'):
        qs = qs.filter(type=txn_type)
    if q:
        qs = qs.filter(Q(description__icontains=q) | Q(category__icontains=q))
    if month:
        try:
            year, mo = month.split('-')
            qs = qs.filter(date__year=year, date__month=mo)
        except ValueError:
            pass

    today = date.today()
    start, end = _month_range(today.year, today.month)
    month_txns  = Transaction.objects.filter(user=request.user, date__gte=start, date__lte=end)
    total_in    = month_txns.filter(type='income').aggregate(s=Sum('amount'))['s']  or Decimal('0')
    total_ex    = month_txns.filter(type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')

    return render(request, 'salary/transactions.html', {
        'transactions': qs,
        'txn_type': txn_type,
        'q': q,
        'month': month,
        'total_income': total_in,
        'total_expense': total_ex,
        'net': total_in - total_ex,
    })


@login_required
def add_transaction(request):
    txn_type = request.GET.get('type', 'income')
    if request.method == 'POST':
        form = TransactionForm(request.POST, txn_type=request.POST.get('type', txn_type))
        if form.is_valid():
            txn = form.save(commit=False)
            txn.user = request.user
            txn.save()
            messages.success(request, f'{txn.get_type_display()} of ₱{txn.amount:,.2f} added.')
            return redirect('transactions')
    else:
        form = TransactionForm(txn_type=txn_type, initial={
            'type': txn_type, 'date': date.today()})
    return render(request, 'salary/transaction_form.html', {
        'form': form, 'txn_type': txn_type,
        'income_cats': INCOME_CATEGORIES, 'expense_cats': EXPENSE_CATEGORIES,
    })


@login_required
def edit_transaction(request, pk):
    txn = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=txn, txn_type=txn.type)
        if form.is_valid():
            form.save()
            messages.success(request, 'Transaction updated.')
            return redirect('transactions')
    else:
        form = TransactionForm(instance=txn, txn_type=txn.type)
    return render(request, 'salary/transaction_form.html', {
        'form': form, 'txn_type': txn.type, 'editing': True,
        'income_cats': INCOME_CATEGORIES, 'expense_cats': EXPENSE_CATEGORIES,
    })


@login_required
def delete_transaction(request, pk):
    txn = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == 'POST':
        txn.delete()
        messages.success(request, 'Transaction deleted.')
        return redirect('transactions')
    return render(request, 'salary/confirm_delete.html', {'object': txn, 'label': 'Transaction'})


# ── Savings ───────────────────────────────────────────────────────────

@login_required
def savings(request):
    goals = SavingsGoal.objects.filter(user=request.user)
    goal_data = [{
        'obj': g, 'percent': g.percent, 'remaining': g.remaining,
        'is_complete': g.is_complete,
        'color': GOAL_COLORS.get(g.category, '#38bdf8'),
        'deposits': g.deposits.all()[:5],
    } for g in goals]
    total_saved = goals.aggregate(s=Sum('current'))['s'] or Decimal('0')
    total_goal  = goals.aggregate(s=Sum('target'))['s']  or Decimal('0')
    return render(request, 'salary/savings.html', {
        'goal_data': goal_data,
        'total_saved': total_saved,
        'total_goal': total_goal,
        'deposit_form': SavingsDepositForm(initial={'date': date.today()}),
    })


@login_required
def add_savings_goal(request):
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f'Goal "{goal.name}" created!')
            return redirect('savings')
    else:
        form = SavingsGoalForm()
    return render(request, 'salary/savings_goal_form.html', {'form': form, 'title': 'New Savings Goal'})


@login_required
def edit_savings_goal(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        form = SavingsGoalForm(request.POST, instance=goal)
        if form.is_valid():
            form.save()
            messages.success(request, 'Goal updated.')
            return redirect('savings')
    else:
        form = SavingsGoalForm(instance=goal)
    return render(request, 'salary/savings_goal_form.html', {'form': form, 'title': 'Edit Goal', 'goal': goal})


@login_required
def delete_savings_goal(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    if request.method == 'POST':
        goal.delete()
        messages.success(request, 'Goal deleted.')
        return redirect('savings')
    return render(request, 'salary/confirm_delete.html', {'object': goal, 'label': 'Savings Goal'})


@login_required
def deposit_savings(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = SavingsDepositForm(request.POST)
        if form.is_valid():
            try:
                # Create unsaved instance
                deposit = form.save(commit=False)
                
                # CRITICAL: Assign the goal BEFORE saving
                deposit.goal = goal
                
                # Now save (this triggers the model's save method which updates the goal)
                deposit.save()
                
                messages.success(request, f'₱{deposit.amount:,.2f} deposited to "{goal.name}".')
                
            except ValidationError as e:
                messages.error(request, str(e))
                return redirect('savings')
            except Exception as e:
                # Catch any other unexpected errors
                messages.error(request, f"An error occurred: {str(e)}")
                return redirect('savings')
                
    return redirect('savings')


# ── Budget ────────────────────────────────────────────────────────────

@login_required
def budget(request):
    today  = date.today()
    start, end = _month_range(today.year, today.month)
    month_txns = Transaction.objects.filter(
        user=request.user, type='expense', date__gte=start, date__lte=end)

    budgets = Budget.objects.filter(user=request.user)
    budget_data = []
    for b in budgets:
        spent = month_txns.filter(category=b.category).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        pct   = min(100, int((spent / b.limit) * 100)) if b.limit > 0 else 0
        budget_data.append({
            'obj': b,
            'spent': spent,
            'remaining': max(Decimal('0'), b.limit - spent),
            'pct': pct,
            'over': spent > b.limit,
            'color': CAT_COLORS.get(b.category, '#64748b'),
        })

    # Categories not yet budgeted
    used_cats = list(budgets.values_list('category', flat=True))
    available_cats = [c for c in EXPENSE_CATEGORIES if c not in used_cats]

    return render(request, 'salary/budget.html', {
        'budget_data': budget_data,
        'available_cats': available_cats,
        'form': BudgetForm(),
        'current_month': today.strftime('%B %Y'),
    })


@login_required
def add_budget(request):
    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            cat = form.cleaned_data['category']
            if Budget.objects.filter(user=request.user, category=cat).exists():
                messages.error(request, f'Budget for {cat} already exists.')
            else:
                b = form.save(commit=False)
                b.user = request.user
                b.save()
                messages.success(request, f'Budget set for {b.category}.')
    return redirect('budget')


@login_required
def edit_budget(request, pk):
    b = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        form = BudgetForm(request.POST, instance=b)
        if form.is_valid():
            form.save()
            messages.success(request, 'Budget updated.')
            return redirect('budget')
    else:
        form = BudgetForm(instance=b)
    return render(request, 'salary/budget_form.html', {'form': form, 'budget': b})


@login_required
def delete_budget(request, pk):
    b = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        b.delete()
        messages.success(request, 'Budget deleted.')
        return redirect('budget')
    return render(request, 'salary/confirm_delete.html', {'object': b, 'label': 'Budget'})


# ── Analytics ─────────────────────────────────────────────────────────

@login_required
def analytics(request):
    today = date.today()

    # 6-month trend
    trend = []
    for i in range(5, -1, -1):
        ref = date(today.year, today.month, 1) - timedelta(days=i * 30)
        ms, me = _month_range(ref.year, ref.month)
        txns = Transaction.objects.filter(user=request.user, date__gte=ms, date__lte=me)
        inc = txns.filter(type='income').aggregate(s=Sum('amount'))['s']  or Decimal('0')
        exp = txns.filter(type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')
        trend.append({'month': ref.strftime('%b %Y'), 'income': float(inc), 'expense': float(exp)})

    # Income by category (all time)
    income_cats = []
    for cat in ['Salary','Freelance','Bonus','Investment','Side Hustle','Gift','Other Income']:
        val = Transaction.objects.filter(user=request.user, type='income', category=cat).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        if val > 0:
            income_cats.append({'name': cat, 'value': float(val), 'color': CAT_COLORS.get(cat, '#64748b')})

    # Expense by category (all time)
    expense_cats = []
    for cat in EXPENSE_CATEGORIES:
        val = Transaction.objects.filter(user=request.user, type='expense', category=cat).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        if val > 0:
            expense_cats.append({'name': cat, 'value': float(val), 'color': CAT_COLORS.get(cat, '#64748b')})

    all_txns = Transaction.objects.filter(user=request.user)
    total_income_all  = all_txns.filter(type='income').aggregate(s=Sum('amount'))['s']  or Decimal('0')
    total_expense_all = all_txns.filter(type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')

    income_months = [t['income'] for t in trend]
    expense_months = [t['expense'] for t in trend]
    avg_income  = sum(income_months) / 6
    avg_expense = sum(expense_months) / 6

    goals = SavingsGoal.objects.filter(user=request.user)
    total_saved = goals.aggregate(s=Sum('current'))['s'] or Decimal('0')

    return render(request, 'salary/analytics.html', {
        'trend_json':       json.dumps(trend),
        'income_cats_json': json.dumps(income_cats),
        'expense_cats_json': json.dumps(expense_cats),
        'total_income_all':  total_income_all,
        'total_expense_all': total_expense_all,
        'avg_income':  avg_income,
        'avg_expense': avg_expense,
        'total_saved': total_saved,
        'total_txns':  all_txns.count(),
        'total_goals': goals.count(),
        'budget_count': Budget.objects.filter(user=request.user).count(),
    })


# ── Profile ───────────────────────────────────────────────────────────

@login_required
def profile(request):
    prof = _get_or_create_profile(request.user)
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=prof)
        if form.is_valid():
            request.user.first_name = form.cleaned_data.get('first_name', request.user.first_name)
            request.user.last_name  = form.cleaned_data.get('last_name',  request.user.last_name)
            request.user.save()
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=prof, initial={
            'first_name': request.user.first_name,
            'last_name':  request.user.last_name,
        })
    return render(request, 'salary/profile.html', {'form': form, 'profile': prof})
@login_required
def deposit_savings(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = SavingsDepositForm(request.POST)
        if form.is_valid():
            try:
                deposit = form.save(commit=False)
                deposit.goal = goal
                # The model's save() method will handle validation and updating the goal
                deposit.save() 
                messages.success(request, f'₱{deposit.amount:,.2f} deposited to "{goal.name}".')
            except ValidationError as e:
                messages.error(request, str(e))
                return redirect('savings')
                
    return redirect('savings')

@login_required
def add_transaction(request):
    txn_type = request.GET.get('type', 'income')
    if request.method == 'POST':
        form = TransactionForm(request.POST, txn_type=request.POST.get('type', txn_type))
        if form.is_valid():
            try:
                txn = form.save(commit=False)
                txn.user = request.user
                # The model's save() method will validate balance for expenses
                txn.save()
                messages.success(request, f'{txn.get_type_display()} of ₱{txn.amount:,.2f} added.')
                return redirect('transactions')
            except ValidationError as e:
                messages.error(request, str(e))
                # Re-render form with error
                return render(request, 'salary/transaction_form.html', {
                    'form': form, 'txn_type': txn_type,
                    'income_cats': INCOME_CATEGORIES, 'expense_cats': EXPENSE_CATEGORIES,
                })
    else:
        form = TransactionForm(txn_type=txn_type, initial={'type': txn_type, 'date': date.today()})
    return render(request, 'salary/transaction_form.html', {
        'form': form, 'txn_type': txn_type,
        'income_cats': INCOME_CATEGORIES, 'expense_cats': EXPENSE_CATEGORIES,
    })