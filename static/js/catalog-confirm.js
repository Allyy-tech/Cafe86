document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('catalog-create-form');
  if (form) {
    form.addEventListener('submit', (event) => {
      const name = form.querySelector('[name="name"]')?.value.trim();
      const message = name
        ? `Add “${name}” to the product catalog?`
        : 'Add this product to the catalog?';
      if (!window.confirm(message)) event.preventDefault();
    });
  }

  document.querySelectorAll('.archive-product-form').forEach((archiveForm) => {
    archiveForm.addEventListener('submit', (event) => {
      const name = archiveForm.dataset.productName || 'this product';
      if (!window.confirm(`Archive “${name}”? It will be hidden from the menu but can be restored from the Archive tab.`)) {
        event.preventDefault();
      }
    });
  });

  document.querySelectorAll('.permanent-delete-form').forEach((deleteForm) => {
    deleteForm.addEventListener('submit', (event) => {
      const name = deleteForm.dataset.productName || 'this product';
      if (!window.confirm(`Permanently delete “${name}”? This cannot be undone.`)) {
        event.preventDefault();
      }
    });
  });
});
