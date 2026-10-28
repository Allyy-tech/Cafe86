/* Manual "Back up now" button on the admin dashboard. */
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('btn-sync');
  if (!btn) return;

  btn.addEventListener('click', async () => {
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = 'Backing up…';
    try {
      const token = await getCsrf();
      const res = await fetch('/api/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        toast(data.message || ('Backed up ' + data.synced + ' transaction(s).'));
        setTimeout(() => window.location.reload(), 900);
        return;
      }
      toast(data.error || 'Backup failed.', true);
    } catch (err) {
      toast('Backup failed. Sales remain safe in the local queue.', true);
    }
    btn.disabled = false;
    btn.textContent = original;
  });
});
