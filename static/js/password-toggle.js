(() => {
  const eyeOpen = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>';
  const eyeClosed = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8"/><path d="M9.9 5.2A10.8 10.8 0 0 1 12 5c6.4 0 10 7 10 7a14.8 14.8 0 0 1-3.1 3.8M6.2 6.2C3.5 8 2 12 2 12s3.6 7 10 7a10.5 10.5 0 0 0 4-.8"/></svg>';

  function addPasswordToggles() {
    document.querySelectorAll('input[type="password"]').forEach((input) => {
      if (input.closest('.password-input-wrap')) return;

      const wrap = document.createElement('div');
      wrap.className = 'password-input-wrap';
      input.parentNode.insertBefore(wrap, input);
      wrap.appendChild(input);
      input.classList.add('password-toggle-input');

      const label = input.labels && input.labels[0] ? input.labels[0].textContent.trim() : '';
      const fieldName = `${label} ${input.name || ''} ${input.id || ''}`.toLowerCase();
      const secretName = fieldName.includes('pin') ? 'PIN' : 'password';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'password-toggle';
      button.setAttribute('aria-label', `Show ${secretName}`);
      button.setAttribute('aria-pressed', 'false');
      button.title = `Show ${secretName}`;
      button.innerHTML = eyeOpen;
      button.addEventListener('click', () => {
        const showing = input.type === 'password';
        input.type = showing ? 'text' : 'password';
        button.innerHTML = showing ? eyeClosed : eyeOpen;
        button.setAttribute('aria-label', `${showing ? 'Hide' : 'Show'} ${secretName}`);
        button.setAttribute('aria-pressed', String(showing));
        button.title = `${showing ? 'Hide' : 'Show'} ${secretName}`;
        input.focus();
      });
      wrap.appendChild(button);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addPasswordToggles, { once: true });
  } else {
    addPasswordToggles();
  }
})();
