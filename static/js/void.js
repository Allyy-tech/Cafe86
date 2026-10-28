/* Binds the void buttons and modal controls. openVoid/closeVoid/confirmVoid
   are defined in pos.js. */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.btn-void').forEach(btn => {
    btn.addEventListener('click', () => openVoid(parseInt(btn.dataset.id, 10)));
  });

  const cancel = document.getElementById('btn-void-cancel');
  if (cancel) cancel.addEventListener('click', closeVoid);

  const confirm = document.getElementById('btn-void-confirm');
  if (confirm) confirm.addEventListener('click', confirmVoid);
});
