// Sidebar mobile toggle
const menuToggle = document.getElementById('menuToggle');
const sidebar    = document.getElementById('sidebar');
if (menuToggle && sidebar) {
  menuToggle.addEventListener('click', () => sidebar.classList.toggle('open'));
  document.addEventListener('click', e => {
    if (!sidebar.contains(e.target) && !menuToggle.contains(e.target))
      sidebar.classList.remove('open');
  });
}

// Auto-dismiss alerts after 4s
document.querySelectorAll('.alert.auto-dismiss').forEach(el => {
  setTimeout(() => el.style.display = 'none', 4000);
});
document.querySelectorAll('.alert-close').forEach(btn => {
  btn.addEventListener('click', () => btn.closest('.alert').style.display = 'none');
});
// static/js/main.js

document.addEventListener('DOMContentLoaded', function() {
  // Get current net balance from a data attribute in your template
  // You need to add <div id="net-balance" data-value="{{ net_balance }}"></div> to your base.html or dashboard
  const balanceEl = document.getElementById('net-balance');
  if (!balanceEl) return;

  const currentBalance = parseFloat(balanceEl.dataset.value);

  // 1. Disable Savings Deposit if balance <= 0
  const savingsForms = document.querySelectorAll('.savings-deposit-form');
  savingsForms.forEach(form => {
      const submitBtn = form.querySelector('button[type="submit"]');
      if (currentBalance <= 0 && submitBtn) {
          submitBtn.disabled = true;
          submitBtn.title = "You need a positive net balance to save.";
          submitBtn.style.opacity = "0.5";
          submitBtn.style.cursor = "not-allowed";
      }
  });

  // 2. Validate Expense Amount on Input
  const expenseInputs = document.querySelectorAll('input[name="amount"]');
  expenseInputs.forEach(input => {
      // Only check if the form is for an expense
      const form = input.closest('form');
      const typeInput = form.querySelector('input[name="type"]');
      
      if (typeInput && typeInput.value === 'expense') {
          input.addEventListener('input', function() {
              const amount = parseFloat(this.value);
              if (amount > currentBalance) {
                  this.setCustomValidity(`Amount exceeds your balance of ₱${currentBalance.toFixed(2)}`);
              } else {
                  this.setCustomValidity('');
              }
          });
      }
  });
});