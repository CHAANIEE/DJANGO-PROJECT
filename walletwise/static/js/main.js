/* ═══════════════════════════════════════════════════════════════
   WalletWise — main.js
   Sidebar, alerts, mobile interactions, micro-animations
   ═══════════════════════════════════════════════════════════════ */

   (function () {
    'use strict';
  
    // ── Sidebar mobile toggle ──────────────────────────────────────
    const menuToggle = document.getElementById('menuToggle');
    const sidebar    = document.getElementById('sidebar');
  
    // Create overlay
    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);
  
    function openSidebar() {
      sidebar.classList.add('open');
      overlay.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  
    function closeSidebar() {
      sidebar.classList.remove('open');
      overlay.classList.remove('active');
      document.body.style.overflow = '';
    }
  
    if (menuToggle && sidebar) {
      menuToggle.addEventListener('click', () => {
        sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
      });
      overlay.addEventListener('click', closeSidebar);
      document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeSidebar();
      });
    }
  
    // ── Auto-dismiss alerts ────────────────────────────────────────
    function dismissAlert(el) {
      el.style.transition = 'opacity .3s ease, transform .3s ease, max-height .3s ease, margin .3s ease, padding .3s ease';
      el.style.opacity = '0';
      el.style.transform = 'translateY(-6px)';
      el.style.maxHeight = '0';
      el.style.marginBottom = '0';
      el.style.padding = '0';
      setTimeout(() => el.remove(), 350);
    }
  
    document.querySelectorAll('.alert.auto-dismiss').forEach(el => {
      setTimeout(() => dismissAlert(el), 5000);
    });
  
    document.querySelectorAll('.alert-close').forEach(btn => {
      btn.addEventListener('click', () => dismissAlert(btn.closest('.alert')));
    });
  
    // ── Animate numbers (stat cards) ──────────────────────────────
    function animateNumber(el) {
      const text = el.textContent.trim();
      const match = text.match(/[₱]?([\d,]+\.?\d*)/);
      if (!match) return;
  
      const raw   = parseFloat(match[1].replace(/,/g, ''));
      if (isNaN(raw) || raw === 0) return;
  
      const prefix = text.includes('₱') ? '₱' : '';
      const decimals = (match[1].split('.')[1] || '').length;
      const duration = 900;
      const start = performance.now();
  
      function tick(now) {
        const t = Math.min((now - start) / duration, 1);
        // easeOutCubic
        const ease = 1 - Math.pow(1 - t, 3);
        const val = raw * ease;
        el.textContent = prefix + val.toLocaleString('en-PH', {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        });
        if (t < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    }
  
    // Animate on page load with IntersectionObserver
    const numEls = document.querySelectorAll('.sc-val, .bh-value, .ss-val, .sb-value');
    if ('IntersectionObserver' in window) {
      const obs = new IntersectionObserver(entries => {
        entries.forEach(e => {
          if (e.isIntersecting) { animateNumber(e.target); obs.unobserve(e.target); }
        });
      }, { threshold: 0.2 });
      numEls.forEach(el => obs.observe(el));
    }
  
    // ── Progress bar entrance animation ───────────────────────────
    document.querySelectorAll('.progress-fill').forEach(bar => {
      const target = bar.style.width;
      bar.style.width = '0';
      setTimeout(() => { bar.style.width = target }, 300);
    });
  
    // ── Active nav link ripple effect ─────────────────────────────
    document.querySelectorAll('.nav-item').forEach(item => {
      item.addEventListener('click', function(e) {
        const ripple = document.createElement('span');
        ripple.style.cssText = `
          position:absolute; border-radius:50%; pointer-events:none;
          background:rgba(245,200,66,.15); transform:scale(0);
          width:80px; height:80px;
          left:${e.offsetX - 40}px; top:${e.offsetY - 40}px;
          animation: ripple .5s ease-out forwards;
        `;
        this.style.position = 'relative';
        this.style.overflow = 'hidden';
        this.appendChild(ripple);
        setTimeout(() => ripple.remove(), 500);
      });
    });
  
    // Add ripple keyframe
    const styleTag = document.createElement('style');
    styleTag.textContent = `
      @keyframes ripple {
        to { transform: scale(3); opacity: 0 }
      }
    `;
    document.head.appendChild(styleTag);
  
    // ── Form input focus enhancement ──────────────────────────────
    document.querySelectorAll('.form-control, .form-select').forEach(input => {
      const group = input.closest('.field-group');
      if (!group) return;
      input.addEventListener('focus', () => group.classList.add('focused'));
      input.addEventListener('blur',  () => group.classList.remove('focused'));
    });
  
    // ── Button press feedback ──────────────────────────────────────
    document.querySelectorAll('.btn').forEach(btn => {
      btn.addEventListener('mousedown', () => btn.style.transform = 'scale(0.97)');
      btn.addEventListener('mouseup',   () => btn.style.transform = '');
      btn.addEventListener('mouseleave',() => btn.style.transform = '');
    });
  
    // ── Table row click highlight ──────────────────────────────────
    document.querySelectorAll('.tbl tbody tr').forEach(row => {
      row.style.cursor = 'default';
    });
  
    // ── Tooltip for truncated text ─────────────────────────────────
    document.querySelectorAll('td, .gc-name, .budget-cat').forEach(el => {
      if (el.scrollWidth > el.clientWidth) {
        el.title = el.textContent.trim();
      }
    });
  
  })();