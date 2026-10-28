/* PIN pad entry. Lives in its own file (not inline) so the Content-Security
   Policy can block inline <script> entirely — one fewer XSS foothold. */

let pinBuffer = '';

function pinRender() {
  for (let i = 0; i < 4; i++) {
    const dot = document.getElementById('d' + i);
    if (dot) dot.className = 'pin-dot' + (i < pinBuffer.length ? ' filled' : '');
  }
}

function pinPress(digit) {
  if (pinBuffer.length >= 4) return;
  pinBuffer += digit;
  pinRender();
  if (pinBuffer.length === 4) {
    document.getElementById('pin-value').value = pinBuffer;
    setTimeout(() => document.getElementById('pin-form').submit(), 120);
  }
}

function pinBack() {
  pinBuffer = pinBuffer.slice(0, -1);
  pinRender();
}

function pinClear() {
  pinBuffer = '';
  pinRender();
}

document.addEventListener('keydown', (e) => {
  if (e.key >= '0' && e.key <= '9') pinPress(e.key);
  else if (e.key === 'Backspace') pinBack();
  else if (e.key === 'Escape') pinClear();
});

document.addEventListener('DOMContentLoaded', pinRender);
