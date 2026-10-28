/* Wires the terminal's buttons to the cart and payment logic in pos.js.
   Uses addEventListener rather than inline onclick="" attributes so the
   Content-Security-Policy can block all inline script. */

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.item-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      addToCart(
        parseInt(btn.dataset.id, 10),
        btn.dataset.name,
        parseFloat(btn.dataset.price)
      );
    });
  });

  const payBtn = document.getElementById('btn-pay');
  if (payBtn) payBtn.addEventListener('click', openPay);

  const clearBtn = document.getElementById('btn-clear');
  if (clearBtn) clearBtn.addEventListener('click', clearCart);

  const cancelBtn = document.getElementById('btn-pay-cancel');
  if (cancelBtn) cancelBtn.addEventListener('click', closePay);

  const confirmBtn = document.getElementById('btn-pay-confirm');
  if (confirmBtn) confirmBtn.addEventListener('click', confirmPay);

  const tendered = document.getElementById('pay-tendered');
  if (tendered) {
    tendered.addEventListener('input', updateChange);
    tendered.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') confirmPay();
    });
  }

  document.querySelectorAll('#pay-methods .seg-btn').forEach(b => {
    b.addEventListener('click', () => setPayMethod(b.dataset.method));
  });

  document.querySelectorAll('#service-types .seg-btn').forEach(b => {
    b.addEventListener('click', () => setServiceType(b.dataset.service));
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePay();
  });
});
