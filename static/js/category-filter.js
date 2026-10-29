document.addEventListener('DOMContentLoaded', () => {
  const buttons = [...document.querySelectorAll('[data-category-filter]')];
  const sections = [...document.querySelectorAll('[data-filter-section]')];
  if (!buttons.length || !sections.length) return;

  buttons.forEach((button) => {
    button.addEventListener('click', () => {
      const selected = button.dataset.categoryFilter;
      buttons.forEach((candidate) => {
        const active = candidate === button;
        candidate.classList.toggle('active', active);
        candidate.setAttribute('aria-pressed', String(active));
      });
      sections.forEach((section) => {
        section.hidden = selected !== 'all' && section.dataset.filterSection !== selected;
      });
    });
  });
});
