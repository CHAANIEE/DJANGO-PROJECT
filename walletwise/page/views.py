from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction as db_transaction
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
import json

from .models import (UserProfile, Transaction, SavingsGoal, SavingsDeposit,
                     Budget, RecurringExpense, AutoSavingsPlan)
from .forms import (RegisterForm, ProfileForm, TransactionForm,
                    SavingsGoalForm, SavingsDepositForm, BudgetForm,
                    RecurringExpenseForm, AutoSavingsPlanForm)
from .scheduler import run_auto_scheduler

INCOME_CATEGORIES  = ['Salary','Freelance','Bonus','Investment','Side Hustle','Gift','Other Income']
EXPENSE_CATEGORIES = ['Food','Rent','Transport','Utilities','Health','Entertainment','Shopping','Education','Other']

CAT_COLORS = {
    'Salary':'#22c55e','Freelance':'#3b82f6','Bonus':'#f59e0b','Investment':'#8b5cf6',
    'Side Hustle':'#06b6d4','Gift':'#ec4899','Other Income':'#10b981',
    'Food':'#ef4444','Rent':'#f97316','Transport':'#eab308','Utilities':'#84cc16',
    'Health':'#14b8a6','Entertainment':'#a855f7','Shopping':'#ec4899',
    'Education':'#6366f1','Savings Deposit':'#38bdf8','Other':'#94a3b8',
    'Emergency Fund':'#22c55e','Retirement':'#3b82f6','Travel':'#f59e0b',
    'House':'#8b5cf6','Car':'#06b6d4',
}
GOAL_COLORS = {
    'Emergency Fund':'#22c55e','Investment':'#3b82f6','Retirement':'#6366f1',
    'Travel':'#f59e0b','House':'#8b5cf6','Car':'#06b6d4','Education':'#ec4899','Other':'#94a3b8',
}


def _extract_error(exc):
    """Extract a clean string from a Django ValidationError."""
    if hasattr(exc, 'message_dict'):
        msgs = []
        for field, errs in exc.message_dict.items():
            msgs.extend(errs)
        return ' '.join(msgs)
    if hasattr(exc, 'messages'):
        return ' '.join(exc.messages)
    return str(exc)


def _get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def _month_range(year, month):
    start = date(year, month, 1)
    end   = date(year + 1, 1, 1) - timedelta(days=1) if month == 12 \
            else date(year, month + 1, 1) - timedelta(days=1)
    return start, end


def _greeting():
    h = timezone.localtime().hour
    return 'Good Morning' if h < 12 else ('Good Afternoon' if h < 17 else 'Good Evening')


# ── Auth ──────────────────────────────────────────────────────────────────────

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
                monthly_salary=form.cleaned_data['monthly_salary'],
                salary_frequency=form.cleaned_data['salary_frequency'],
            )
            login(request, user)
            messages.success(request, f'Welcome to WalletWise, {user.first_name}!')
            return redirect('dashboard')
    else:
        form = RegisterForm()
    return render(request, 'salary/register.html', {'form': form})


# ── Dashboard ─────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    profile = _get_or_create_profile(request.user)
    today   = date.today()

    # Run auto-scheduler
    auto_log = run_auto_scheduler(request.user)
    for msg in auto_log:
        messages.info(request, msg)

    start, end = _month_range(today.year, today.month)
    month_txns = Transaction.objects.filter(
        user=request.user, date__gte=start, date__lte=end)

    total_income  = month_txns.filter(type='income').aggregate(s=Sum('amount'))['s']  or Decimal('0')
    total_expense = month_txns.filter(type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    net_balance   = total_income - total_expense
    total_saved   = SavingsGoal.objects.filter(user=request.user).aggregate(s=Sum('current'))['s'] or Decimal('0')

    # Next salary countdown
    release_days = [1] if profile.salary_frequency == 'monthly' else [1, 16]
    next_salary_day = None
    for d in release_days:
        if today.day <= d:
            next_salary_day = date(today.year, today.month, d)
            break
    if next_salary_day is None:
        m = today.month + 1 if today.month < 12 else 1
        y = today.year if today.month < 12 else today.year + 1
        next_salary_day = date(y, m, release_days[0])
    days_until_salary = (next_salary_day - today).days

    # Monthly plan totals
    rec_expenses       = RecurringExpense.objects.filter(user=request.user, is_active=True)
    auto_savings       = AutoSavingsPlan.objects.filter(user=request.user, is_active=True)
    total_rec_monthly  = sum(e.monthly_cost for e in rec_expenses)
    total_auto_savings = sum(p.monthly_cost for p in auto_savings)
    disposable         = profile.monthly_salary - total_rec_monthly - total_auto_savings

    # 6-month trend
    trend = []
    for i in range(5, -1, -1):
        ref = date(today.year, today.month, 1) - timedelta(days=i * 30)
        ms, me = _month_range(ref.year, ref.month)
        txns = Transaction.objects.filter(user=request.user, date__gte=ms, date__lte=me)
        inc  = txns.filter(type='income').aggregate(s=Sum('amount'))['s']  or Decimal('0')
        exp  = txns.filter(type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')
        trend.append({'month': ref.strftime('%b %Y'), 'income': float(inc), 'expense': float(exp)})

    # Expense donut
    exp_cats = []
    for cat in EXPENSE_CATEGORIES + ['Savings Deposit']:
        val = month_txns.filter(type='expense', category=cat).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        if val > 0:
            exp_cats.append({'name': cat, 'value': float(val), 'color': CAT_COLORS.get(cat, '#64748b')})

    # Budget progress
    budgets = Budget.objects.filter(user=request.user)
    budget_data = []
    for b in budgets:
        spent = month_txns.filter(type='expense', category=b.category).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        pct   = min(100, int((spent / b.limit) * 100)) if b.limit > 0 else 0
        budget_data.append({
            'obj': b, 'spent': spent,
            'remaining': max(Decimal('0'), b.limit - spent),
            'pct': pct, 'over': spent > b.limit,
            'color': CAT_COLORS.get(b.category, '#64748b'),
        })

    # Goals
    goals = SavingsGoal.objects.filter(user=request.user)
    goal_data = [{
        'id': g.id, 'name': g.name, 'category': g.category,
        'target': g.target, 'current': g.current,
        'percent': g.percent, 'remaining': g.remaining,
        'is_complete': g.is_complete,
        'color': GOAL_COLORS.get(g.category, '#38bdf8'),
    } for g in goals]

    recent = Transaction.objects.filter(user=request.user)[:8]

    return render(request, 'salary/dashboard.html', {
        'profile':             profile,
        'total_income':        total_income,
        'total_expense':       total_expense,
        'net_balance':         net_balance,
        'total_saved':         total_saved,
        'trend_json':          json.dumps(trend),
        'exp_cats_json':       json.dumps(exp_cats),
        'budget_data':         budget_data,
        'goal_data':           goal_data,
        'recent':              recent,
        'current_month':       today.strftime('%B %Y'),
        'greeting':            _greeting(),
        'next_salary_day':     next_salary_day,
        'days_until_salary':   days_until_salary,
        'total_rec_monthly':   total_rec_monthly,
        'total_auto_savings':  total_auto_savings,
        'disposable':          disposable,
    })


# ── Transactions ──────────────────────────────────────────────────────────────

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
    month_txns = Transaction.objects.filter(user=request.user, date__gte=start, date__lte=end)
    total_in   = month_txns.filter(type='income').aggregate(s=Sum('amount'))['s']  or Decimal('0')
    total_ex   = month_txns.filter(type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')
    return render(request, 'salary/transactions.html', {
        'transactions': qs, 'txn_type': txn_type, 'q': q, 'month': month,
        'total_income': total_in, 'total_expense': total_ex, 'net': total_in - total_ex,
    })


@login_required
def add_transaction(request):
    txn_type = request.GET.get('type', 'income')
    if request.method == 'POST':
        form = TransactionForm(request.POST, txn_type=request.POST.get('type', txn_type))
        if form.is_valid():
            try:
                txn = form.save(commit=False)
                txn.user = request.user
                txn.save()
                messages.success(request, f'{txn.get_type_display()} of ₱{txn.amount:,.2f} added.')
                return redirect('transactions')
            except ValidationError as e:
                messages.error(request, _extract_error(e))
    else:
        form = TransactionForm(txn_type=txn_type, initial={'type': txn_type, 'date': date.today()})
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
            try:
                form.save()
                messages.success(request, 'Transaction updated.')
                return redirect('transactions')
            except ValidationError as e:
                messages.error(request, _extract_error(e))
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


# ── Savings ───────────────────────────────────────────────────────────────────

@login_required
def savings(request):
    goals = SavingsGoal.objects.filter(user=request.user)
    goal_data = [{
        'obj': g, 'percent': g.percent, 'remaining': g.remaining,
        'is_complete': g.is_complete,
        'color': GOAL_COLORS.get(g.category, '#38bdf8'),
        'deposits': g.deposits.all()[:5],
        'auto_plans': g.auto_plans.filter(is_active=True),
    } for g in goals]
    total_saved = goals.aggregate(s=Sum('current'))['s'] or Decimal('0')
    total_goal  = goals.aggregate(s=Sum('target'))['s']  or Decimal('0')
    return render(request, 'salary/savings.html', {
        'goal_data': goal_data, 'total_saved': total_saved, 'total_goal': total_goal,
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
                with db_transaction.atomic():
                    deposit = form.save(commit=False)
                    deposit.goal = goal
                    deposit.save()  # validates + updates goal.current
                    # Log as expense transaction (skip balance re-check, already validated above)
                    t = Transaction(
                        user=request.user, type='expense', category='Savings Deposit',
                        amount=deposit.amount,
                        description=f'Manual deposit → {goal.name}',
                        date=deposit.date,
                    )
                    t.save(skip_validation=True)
                messages.success(request, f'₱{deposit.amount:,.2f} deposited to "{goal.name}".')
            except ValidationError as e:
                messages.error(request, _extract_error(e))
    return redirect('savings')


# ── Auto Savings Plans ────────────────────────────────────────────────────────

@login_required
def auto_savings_plans(request):
    plans = AutoSavingsPlan.objects.filter(user=request.user).select_related('goal')
    form  = AutoSavingsPlanForm(user=request.user)
    return render(request, 'salary/auto_savings.html', {'plans': plans, 'form': form})


@login_required
def add_auto_savings(request):
    if request.method == 'POST':
        form = AutoSavingsPlanForm(request.user, request.POST)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.user = request.user
            plan.save()
            messages.success(request, f'Auto-savings plan created for "{plan.goal.name}".')
    return redirect('auto_savings_plans')


@login_required
def delete_auto_savings(request, pk):
    plan = get_object_or_404(AutoSavingsPlan, pk=pk, user=request.user)
    if request.method == 'POST':
        plan.delete()
        messages.success(request, 'Plan removed.')
        return redirect('auto_savings_plans')
    return render(request, 'salary/confirm_delete.html', {'object': plan, 'label': 'Auto-Savings Plan'})


@login_required
def toggle_auto_savings(request, pk):
    plan = get_object_or_404(AutoSavingsPlan, pk=pk, user=request.user)
    plan.is_active = not plan.is_active
    plan.save(update_fields=['is_active'])
    messages.success(request, f'Plan {"activated" if plan.is_active else "paused"}.')
    return redirect('auto_savings_plans')


# ── Recurring Expenses ────────────────────────────────────────────────────────

@login_required
def recurring_expenses(request):
    expenses = RecurringExpense.objects.filter(user=request.user)
    form     = RecurringExpenseForm()
    total_monthly = sum(e.monthly_cost for e in expenses if e.is_active)
    return render(request, 'salary/recurring.html', {
        'expenses': expenses, 'form': form, 'total_monthly': total_monthly,
    })


@login_required
def add_recurring(request):
    if request.method == 'POST':
        form = RecurringExpenseForm(request.POST)
        if form.is_valid():
            exp = form.save(commit=False)
            exp.user = request.user
            exp.save()
            messages.success(request, f'"{exp.name}" added to recurring expenses.')
    return redirect('recurring_expenses')


@login_required
def edit_recurring(request, pk):
    exp = get_object_or_404(RecurringExpense, pk=pk, user=request.user)
    if request.method == 'POST':
        form = RecurringExpenseForm(request.POST, instance=exp)
        if form.is_valid():
            form.save()
            messages.success(request, 'Updated.')
            return redirect('recurring_expenses')
    else:
        form = RecurringExpenseForm(instance=exp)
    return render(request, 'salary/recurring_form.html', {'form': form, 'exp': exp})


@login_required
def delete_recurring(request, pk):
    exp = get_object_or_404(RecurringExpense, pk=pk, user=request.user)
    if request.method == 'POST':
        exp.delete()
        messages.success(request, 'Deleted.')
        return redirect('recurring_expenses')
    return render(request, 'salary/confirm_delete.html', {'object': exp, 'label': 'Recurring Expense'})


@login_required
def toggle_recurring(request, pk):
    exp = get_object_or_404(RecurringExpense, pk=pk, user=request.user)
    exp.is_active = not exp.is_active
    exp.save(update_fields=['is_active'])
    messages.success(request, f'"{exp.name}" {"activated" if exp.is_active else "paused"}.')
    return redirect('recurring_expenses')


# ── Budget ────────────────────────────────────────────────────────────────────

@login_required
def budget(request):
    today = date.today()
    start, end = _month_range(today.year, today.month)
    month_txns = Transaction.objects.filter(
        user=request.user, type='expense', date__gte=start, date__lte=end)
    budgets = Budget.objects.filter(user=request.user)
    budget_data = []
    for b in budgets:
        spent = month_txns.filter(category=b.category).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        pct   = min(100, int((spent / b.limit) * 100)) if b.limit > 0 else 0
        budget_data.append({
            'obj': b, 'spent': spent,
            'remaining': max(Decimal('0'), b.limit - spent),
            'pct': pct, 'over': spent > b.limit,
            'color': CAT_COLORS.get(b.category, '#64748b'),
        })
    used_cats      = list(budgets.values_list('category', flat=True))
    available_cats = [c for c in EXPENSE_CATEGORIES if c not in used_cats]
    return render(request, 'salary/budget.html', {
        'budget_data': budget_data, 'available_cats': available_cats,
        'form': BudgetForm(), 'current_month': today.strftime('%B %Y'),
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


# ── Analytics ─────────────────────────────────────────────────────────────────

@login_required
def analytics(request):
    today = date.today()
    trend = []
    for i in range(5, -1, -1):
        ref = date(today.year, today.month, 1) - timedelta(days=i * 30)
        ms, me = _month_range(ref.year, ref.month)
        txns = Transaction.objects.filter(user=request.user, date__gte=ms, date__lte=me)
        inc  = txns.filter(type='income').aggregate(s=Sum('amount'))['s']  or Decimal('0')
        exp  = txns.filter(type='expense').aggregate(s=Sum('amount'))['s'] or Decimal('0')
        trend.append({'month': ref.strftime('%b %Y'), 'income': float(inc), 'expense': float(exp)})

    income_cats, expense_cats = [], []
    for cat in INCOME_CATEGORIES:
        val = Transaction.objects.filter(
            user=request.user, type='income', category=cat
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        if val > 0:
            income_cats.append({'name': cat, 'value': float(val), 'color': CAT_COLORS.get(cat, '#64748b')})
    for cat in EXPENSE_CATEGORIES + ['Savings Deposit']:
        val = Transaction.objects.filter(
            user=request.user, type='expense', category=cat
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0')
        if val > 0:
            expense_cats.append({'name': cat, 'value': float(val), 'color': CAT_COLORS.get(cat, '#64748b')})

    all_txns    = Transaction.objects.filter(user=request.user)
    goals       = SavingsGoal.objects.filter(user=request.user)
    total_saved = goals.aggregate(s=Sum('current'))['s'] or Decimal('0')
    income_months  = [t['income']  for t in trend]
    expense_months = [t['expense'] for t in trend]
    avg_income  = sum(income_months)  / 6
    avg_expense = sum(expense_months) / 6

    return render(request, 'salary/analytics.html', {
        'trend_json':        json.dumps(trend),
        'income_cats_json':  json.dumps(income_cats),
        'expense_cats_json': json.dumps(expense_cats),
        'avg_income':        avg_income,
        'avg_expense':       avg_expense,
        'total_saved':       total_saved,
        'total_txns':        all_txns.count(),
    })


# ── Profile ───────────────────────────────────────────────────────────────────

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
            messages.success(request, 'Profile updated.')
            return redirect('dashboard')
    else:
        form = ProfileForm(instance=prof, initial={
            'first_name': request.user.first_name,
            'last_name':  request.user.last_name,
        })
    return render(request, 'salary/profile.html', {'form': form, 'profile': prof})