/* Secure Cafe POS — terminal behaviour */

let csrfToken = null;

async function getCsrf() {
  if (csrfToken) return csrfToken;
  const res = await fetch('/api/csrf-token');
  const data = await res.json();
  csrfToken = data.token;
  return csrfToken;
}

function peso(n) {
  return '\u20b1' + Number(n).toFixed(2);
}

function toast(msg, bad) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = 'toast show' + (bad ? ' bad' : '');
  setTimeout(() => { el.className = 'toast' + (bad ? ' bad' : ''); }, 3200);
}

/* ------------------------------------------------------------ cart */

const cart = [];

function cartTotal() {
  return cart.reduce((sum, l) => sum + l.price * l.quantity, 0);
}

function addToCart(id, name, price) {
  const found = cart.find(l => l.menu_item_id === id);
  if (found) {
    if (found.quantity >= 50) { toast('Maximum quantity reached for this item.', true); return; }
    found.quantity += 1;
  } else {
    cart.push({ menu_item_id: id, name: name, price: price, quantity: 1 });
  }
  renderCart();
}

function changeQty(id, delta) {
  const line = cart.find(l => l.menu_item_id === id);
  if (!line) return;
  line.quantity += delta;
  if (line.quantity <= 0) cart.splice(cart.indexOf(line), 1);
  renderCart();
}

function clearCart() {
  cart.length = 0;
  renderCart();
}

function renderCart() {
  const body = document.getElementById('cart-body');
  const foot = document.getElementById('cart-foot');
  const count = document.getElementById('cart-count');
  if (!body) return;

  if (cart.length === 0) {
    body.innerHTML = '<div class="cart-empty">No items yet.<br>Tap a product to start an order.</div>';
    foot.style.display = 'none';
    count.textContent = '0 items';
    return;
  }

  body.innerHTML = '';
  let subtotal = 0;
  let units = 0;

  cart.forEach(line => {
    const lineTotal = line.price * line.quantity;
    subtotal += lineTotal;
    units += line.quantity;

    const row = document.createElement('div');
    row.className = 'cart-line';

    const info = document.createElement('div');
    info.className = 'info';
    const nm = document.createElement('span');
    nm.className = 'nm';
    nm.textContent = line.name;                 // textContent, never innerHTML —
    const ea = document.createElement('span');  // item names are escaped by
    ea.className = 'ea';                        // construction, not by hope
    ea.textContent = peso(line.price) + ' each';
    info.appendChild(nm);
    info.appendChild(ea);

    const qty = document.createElement('div');
    qty.className = 'qty';
    const minus = document.createElement('button');
    minus.type = 'button';
    minus.textContent = '\u2212';
    minus.onclick = () => changeQty(line.menu_item_id, -1);
    const n = document.createElement('span');
    n.className = 'n';
    n.textContent = line.quantity;
    const plus = document.createElement('button');
    plus.type = 'button';
    plus.textContent = '+';
    plus.onclick = () => changeQty(line.menu_item_id, 1);
    qty.appendChild(minus); qty.appendChild(n); qty.appendChild(plus);

    const lt = document.createElement('div');
    lt.className = 'lt';
    lt.textContent = peso(lineTotal);

    row.appendChild(info); row.appendChild(qty); row.appendChild(lt);
    body.appendChild(row);
  });

  const vatRate = 0.12;
  const net = subtotal / (1 + vatRate);
  document.getElementById('sum-net').textContent = peso(net);
  document.getElementById('sum-vat').textContent = peso(subtotal - net);
  document.getElementById('sum-total').textContent = peso(subtotal);
  count.textContent = units + (units === 1 ? ' item' : ' items');
  foot.style.display = 'block';
}

/* ------------------------------------------------------------ payment

   The change shown here is a live convenience for the cashier. The server
   recomputes it independently at checkout and stores its own figure — the
   browser's number is never trusted. */

let payMethod = 'cash';
let serviceType = 'dine_in';

function roundUpTo(value, step) {
  return Math.ceil(value / step) * step;
}

function openPay() {
  if (cart.length === 0) return;
  const total = cartTotal();
  payMethod = 'cash';
  serviceType = 'dine_in';

  document.getElementById('pay-due').textContent = peso(total);
  document.getElementById('pay-error').style.display = 'none';
  document.getElementById('pay-tendered').value = '';
  document.getElementById('pay-change').textContent = peso(0);
  document.getElementById('cash-section').style.display = 'block';
  document.getElementById('gcash-section').style.display = 'none';

  document.querySelectorAll('#service-types .seg-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.service === serviceType);
  });

  document.querySelectorAll('#pay-methods .seg-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.method === 'cash');
  });

  // Quick-tender buttons: exact amount, then the next sensible notes up.
  const quick = document.getElementById('quick-cash');
  quick.innerHTML = '';
  const options = [total, roundUpTo(total, 50), roundUpTo(total, 100), roundUpTo(total, 500), 1000];
  const seen = [];
  options.forEach(v => {
    const rounded = Math.round(v * 100) / 100;
    if (rounded >= total && !seen.includes(rounded) && seen.length < 4) {
      seen.push(rounded);
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'btn btn-sm';
      b.textContent = rounded === total ? 'Exact' : peso(rounded);
      b.onclick = () => {
        document.getElementById('pay-tendered').value = rounded.toFixed(2);
        updateChange();
      };
      quick.appendChild(b);
    }
  });

  document.getElementById('pay-modal').classList.add('show');
  setTimeout(() => document.getElementById('pay-tendered').focus(), 60);
}

function closePay() {
  document.getElementById('pay-modal').classList.remove('show');
}

function updateChange() {
  const total = cartTotal();
  const tendered = parseFloat(document.getElementById('pay-tendered').value);
  const box = document.getElementById('pay-change');
  if (isNaN(tendered) || tendered < total) {
    box.textContent = peso(0);
    box.className = 'mono';
  } else {
    box.textContent = peso(tendered - total);
    box.className = 'mono ok';
  }
}

function setPayMethod(method) {
  payMethod = method;
  document.querySelectorAll('#pay-methods .seg-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.method === method);
  });
  document.getElementById('cash-section').style.display = method === 'cash' ? 'block' : 'none';
  document.getElementById('gcash-section').style.display = method === 'ewallet' ? 'flex' : 'none';
  document.getElementById('pay-error').style.display = 'none';
}

function setServiceType(type) {
  serviceType = type;
  document.querySelectorAll('#service-types .seg-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.service === type);
  });
}

async function confirmPay() {
  const total = cartTotal();
  const errBox = document.getElementById('pay-error');
  let tendered = total;

  if (payMethod === 'cash') {
    tendered = parseFloat(document.getElementById('pay-tendered').value);
    if (isNaN(tendered)) {
      errBox.textContent = 'Enter the cash amount received.';
      errBox.style.display = 'block';
      return;
    }
    if (tendered < total) {
      errBox.textContent = 'Cash received is less than the total due.';
      errBox.style.display = 'block';
      return;
    }
  }

  const btn = document.getElementById('btn-pay-confirm');
  btn.disabled = true;
  btn.textContent = 'Processing...';

  try {
    const token = await getCsrf();
    const res = await fetch('/pos/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
      body: JSON.stringify({
        cart: cart,
        payment_method: payMethod,
        service_type: serviceType,
        amount_tendered: tendered
      })
    });
    const data = await res.json();

    if (res.ok && data.success) {
      clearCart();
      window.location = '/pos/receipt/' + data.transaction_id;
      return;
    }
    errBox.textContent = data.error || 'Could not complete the sale.';
    errBox.style.display = 'block';
  } catch (err) {
    // A failure here means the LOCAL link to the server is down, which is a
    // different (and much rarer) problem than the internet being out.
    errBox.textContent = 'Cannot reach the café server. Check the local Wi-Fi connection.';
    errBox.style.display = 'block';
  }

  btn.disabled = false;
  btn.textContent = 'Complete Sale';
}

/* ------------------------------------------------------------ void */

let voidTargetId = null;

function openVoid(id) {
  voidTargetId = id;
  document.getElementById('void-txn-id').textContent = '#' + id;
  document.getElementById('void-pin').value = '';
  document.getElementById('void-reason').value = '';
  document.getElementById('void-error').style.display = 'none';
  document.getElementById('void-modal').classList.add('show');
}

function closeVoid() {
  document.getElementById('void-modal').classList.remove('show');
  voidTargetId = null;
}

async function confirmVoid() {
  const pin = document.getElementById('void-pin').value;
  const reason = document.getElementById('void-reason').value;
  const errBox = document.getElementById('void-error');

  try {
    const token = await getCsrf();
    const res = await fetch('/pos/void/' + voidTargetId, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
      body: JSON.stringify({ manager_pin: pin, reason: reason })
    });
    const data = await res.json();

    if (res.ok && data.success) {
      closeVoid();
      window.location.reload();
      return;
    }
    errBox.textContent = data.error || 'Could not void this transaction.';
    errBox.style.display = 'block';
  } catch (err) {
    errBox.textContent = 'Cannot reach the café server. Check the local Wi-Fi connection.';
    errBox.style.display = 'block';
  }
}

/* ------------------------------------------------------------ offline badge

   Polls only to update the ONLINE/OFFLINE indicator. Nothing about selling
   depends on the result — if this request fails entirely we just show
   OFFLINE and the register carries on taking orders exactly as before. */

async function pollStatus() {
  const badge = document.getElementById('status-badge');
  if (!badge) return;

  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const pendingTxt = data.pending > 0 ? ' \u00b7 ' + data.pending + ' queued' : '';
    if (data.online) {
      badge.className = 'status-badge status-online';
      badge.innerHTML = '<span class="dot"></span>ONLINE' + pendingTxt;
    } else {
      badge.className = 'status-badge status-offline';
      badge.innerHTML = '<span class="dot"></span>OFFLINE MODE' + pendingTxt;
    }
  } catch (err) {
    badge.className = 'status-badge status-offline';
    badge.innerHTML = '<span class="dot"></span>OFFLINE MODE';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  renderCart();
  pollStatus();
  setInterval(pollStatus, 15000);
});
