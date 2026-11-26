/**
 * Shared UI helpers (HTML escaping and accessible toast notifications).
 */
(function (global) {
  function escapeHtml(str) {
    return String(str || '').replace(/[&<>'"]/g, (ch) => {
      switch (ch) {
        case '&':
          return '&amp;';
        case '<':
          return '&lt;';
        case '>':
          return '&gt;';
        case "'":
          return '&#39;';
        case '"':
          return '&quot;';
        default:
          return ch;
      }
    });
  }

  function showToast(message, type = 'error', duration = 4500) {
    let toast = document.getElementById('ivToast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'ivToast';
      toast.className = 'iv-toast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      document.body.appendChild(toast);
    }
    toast.className = `iv-toast ${type} show`;
    toast.textContent = message;
    clearTimeout(global._ivToastTimeout);
    global._ivToastTimeout = setTimeout(() => {
      toast.classList.remove('show');
    }, duration);
  }

  global.ResuMateUI = { escapeHtml, showToast };
})(window);
