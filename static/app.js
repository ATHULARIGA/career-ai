// ResuMate Application Scripts (Theme toggle and scroll reveal animations)
(function () {
  const root = document.documentElement;
  const key = "resumate-theme";
  const saved = localStorage.getItem(key);
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  const initialTheme = saved || (prefersDark ? "dark" : "light");

  function applyTheme(theme) {
    const isDark = (theme === "dark");
    if (isDark) {
      root.classList.add("theme-dark");
    } else {
      root.classList.remove("theme-dark");
    }
    const btn = document.getElementById("themeToggle");
    if (btn) {
      btn.textContent = isDark ? "Light" : "Dark";
    }
  }

  applyTheme(initialTheme);

  function initInteractive() {
    const btn = document.getElementById("themeToggle");
    if (btn) {
      btn.addEventListener("click", function () {
        const next = root.classList.contains("theme-dark") ? "light" : "dark";
        localStorage.setItem(key, next);
        applyTheme(next);
      });
    }

    const items = document.querySelectorAll(".reveal-on-scroll");
    if (items.length > 0) {
      if (!("IntersectionObserver" in window)) {
        items.forEach(function (item) { item.classList.add("is-visible"); });
        return;
      }
      const observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.12 });
      items.forEach(function (item) { observer.observe(item); });
    }
  }

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", initInteractive);
  } else {
    initInteractive();
  }
})();
