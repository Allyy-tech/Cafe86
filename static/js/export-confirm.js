document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.export-confirm').forEach((link) => {
    link.addEventListener('click', (event) => {
      const period = link.dataset.exportPeriod || 'selected period';
      if (!window.confirm(`Export ${period} transactions to Excel? The workbook will download to your device.`)) {
        event.preventDefault();
      }
    });
  });
});
