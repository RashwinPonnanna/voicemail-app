// Auto-dismiss alerts after 5 seconds
document.querySelectorAll('.alert').forEach(el => {
  setTimeout(() => el.remove(), 5000);
});
