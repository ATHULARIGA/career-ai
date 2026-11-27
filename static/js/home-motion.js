/**
 * Minimal, one-time Anime.js v4 motion for the ResuMate landing page.
 * Respects prefers-reduced-motion and preserves immediate first paint for LCP.
 */
(function () {
  function initHomeMotion() {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }
    const animeApi = window.anime;
    if (!animeApi || typeof animeApi.animate !== 'function') {
      return;
    }
    const { animate, stagger } = animeApi;

    // 1. One-time hero score ring & progress bar fill
    const ring = document.querySelector('.hero-telemetry-ring');
    if (ring) {
      animate(ring, {
        strokeDashoffset: [100, 8],
        duration: 900,
        ease: 'outExpo',
      });
    }

    const bars = document.querySelectorAll('.telemetry-bar-fill');
    if (bars.length) {
      animate(bars, {
        width: ['0%', (el) => el.dataset.target || '88%'],
        duration: 850,
        delay: stagger(100),
        ease: 'outExpo',
      });
    }

    // 2. Gentle one-time scroll stagger on capability & feature grids
    const grids = document.querySelectorAll('.capabilities-grid-3, .capabilities-grid-2, .feature-grid-3');
    if ('IntersectionObserver' in window && grids.length) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            const cards = entry.target.querySelectorAll('.clean-card, .feature-card-detailed');
            if (cards.length) {
              animate(cards, {
                translateY: [12, 0],
                duration: 480,
                delay: stagger(60),
                ease: 'outQuad',
              });
            }
            observer.unobserve(entry.target);
          });
        },
        { threshold: 0.15 }
      );
      grids.forEach((grid) => observer.observe(grid));
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHomeMotion);
  } else {
    initHomeMotion();
  }
})();
