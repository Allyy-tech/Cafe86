document.addEventListener('DOMContentLoaded', () => {
  const b = document.getElementById('btn-print');
  if (b) b.addEventListener('click', () => window.print());
});
