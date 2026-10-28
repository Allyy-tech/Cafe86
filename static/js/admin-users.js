/* Admins need an email and password; staff need a username and PIN, and
 * may use an email as an alternate sign-in identifier.
 * Toggling `required` alongside display matters — a required field hidden
 * only via CSS still blocks submission in most browsers. */

function applyStaffRoleMode() {
  const role = document.getElementById('role').value;
  const isAdmin = role === 'admin';

  const usernameGroup = document.getElementById('username-group');
  const emailGroup = document.getElementById('email-group');
  const passwordGroup = document.getElementById('password-group');
  const usernameInput = document.getElementById('username');
  const emailInput = document.getElementById('email');
  const emailHint = document.getElementById('email-hint');

  usernameGroup.style.display = isAdmin ? 'none' : 'block';
  emailGroup.style.display = 'block';
  passwordGroup.style.display = isAdmin ? 'block' : 'none';

  usernameInput.required = !isAdmin;
  emailInput.required = isAdmin;
  emailHint.textContent = isAdmin
    ? 'Required for admin sign-in and password recovery.'
    : 'Optional for staff; when provided, they may sign in using this email.';

  if (isAdmin) usernameInput.value = '';
}

document.addEventListener('DOMContentLoaded', () => {
  const roleSelect = document.getElementById('role');
  if (!roleSelect) return;
  roleSelect.addEventListener('change', applyStaffRoleMode);
  applyStaffRoleMode();
});
