"""
WalletWise Auto-Scheduler
Called on every dashboard load.
  1. Auto salary deposit   — monthly (1st) or semi-monthly (1st & 16th)
  2. Auto recurring expenses — deducted on their schedule
  3. Auto savings plans     — daily / semi-monthly / monthly
"""
from datetime import date
from decimal import Decimal

from .models import (
    UserProfile, Transaction, RecurringExpense,
    AutoSavingsPlan, SavingsDeposit,
)


def _already_posted(user, auto_tag, for_date):
    """True if this exact auto entry was already created today."""
    return Transaction.objects.filter(
        user=user, auto_tag=auto_tag, date=for_date
    ).exists()


def _salary_due(profile, today):
    release_days = [1] if profile.salary_frequency == 'monthly' else [1, 16]
    if today.day not in release_days:
        return False
    tag = f"auto_salary_{today.strftime('%Y%m%d')}"
    return not _already_posted(profile.user, tag, today)


def _expense_due(expense, today):
    release_days = [1] if expense.frequency == 'monthly' else [1, 16]
    if today.day not in release_days:
        return False
    tag = f"auto_exp_{expense.pk}_{today.strftime('%Y%m%d')}"
    return not _already_posted(expense.user, tag, today)


def _savings_due(plan, today):
    if plan.frequency == 'daily':
        pass  # every day — just check the tag below
    elif plan.frequency == 'semi':
        if today.day not in [1, 16]:
            return False
    else:  # monthly
        if today.day != 1:
            return False
    tag = f"auto_sav_{plan.pk}_{today.strftime('%Y%m%d')}"
    return not _already_posted(plan.user, tag, today)


def run_auto_scheduler(user):
    """Run all auto tasks for a user. Returns list of notification messages."""
    today   = date.today()
    profile = UserProfile.objects.get(user=user)
    log     = []

    # ── 1. Auto Salary ──────────────────────────────────────────────
    if profile.monthly_salary > 0 and _salary_due(profile, today):
        amount = profile.salary_per_release
        tag    = f"auto_salary_{today.strftime('%Y%m%d')}"
        label  = 'Semi-monthly Salary' if profile.salary_frequency == 'semi' else 'Monthly Salary'
        Transaction.objects.create(
            user=user, type='income', category='Salary',
            amount=amount,
            description=f'[Auto] {label} — {today.strftime("%b %d, %Y")}',
            date=today,
            auto_tag=tag,
        )
        profile.last_salary_date = today
        profile.save(update_fields=['last_salary_date'])
        log.append(f'✅ Auto Salary credited: ₱{amount:,.2f}')

    # ── 2. Auto Recurring Expenses ───────────────────────────────────
    for exp in RecurringExpense.objects.filter(user=user, is_active=True):
        if _expense_due(exp, today):
            tag = f"auto_exp_{exp.pk}_{today.strftime('%Y%m%d')}"
            # Use skip_validation=True so balance-check doesn't block auto entries
            t = Transaction(
                user=user, type='expense', category=exp.category,
                amount=exp.amount,
                description=f'[Auto] {exp.name}',
                date=today,
                auto_tag=tag,
            )
            t.save(skip_validation=True)
            log.append(f'💸 Auto Expense: {exp.name} — ₱{exp.amount:,.2f}')

    # ── 3. Auto Savings Plans ────────────────────────────────────────
    for plan in AutoSavingsPlan.objects.filter(
            user=user, is_active=True).select_related('goal'):
        if _savings_due(plan, today):
            tag  = f"auto_sav_{plan.pk}_{today.strftime('%Y%m%d')}"
            goal = plan.goal
            if goal.is_complete:
                continue
            deposit_amt = min(plan.amount, goal.remaining)

            # Expense from wallet
            t = Transaction(
                user=user, type='expense', category='Savings Deposit',
                amount=deposit_amt,
                description=f'[Auto] Savings → {goal.name}',
                date=today,
                auto_tag=tag,
            )
            t.save(skip_validation=True)

            # Credit savings goal (is_auto=True skips balance re-check)
            SavingsDeposit.objects.create(
                goal=goal,
                amount=deposit_amt,
                note=f'Auto deposit ({plan.get_frequency_display()})',
                date=today,
                is_auto=True,
            )
            plan.last_run = today
            plan.save(update_fields=['last_run'])
            log.append(f'🐷 Auto Savings: ₱{deposit_amt:,.2f} → {goal.name}')

    return log