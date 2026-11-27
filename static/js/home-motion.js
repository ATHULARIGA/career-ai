/**
 * Responsive scroll-driven "Resume Opening & Closing" animation for ResuMate.
 * Smoothly unfolds as the user scrolls down and folds closed as they scroll back up.
 */
(function () {
  function initHomeMotion() {
    const stage = document.getElementById('resumeScrollStage');
    const sheetExp = document.querySelector('.sheet-experience');
    const sheetVerdict = document.querySelector('.sheet-verdict');
    const ring = document.querySelector('.hero-telemetry-ring');
    const scoreEl = document.querySelector('.telemetry-score-num');
    const foldLabel = document.getElementById('resumeFoldState');
    const bars = document.querySelectorAll('.telemetry-bar-fill');

    const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reducedMotion) {
      if (sheetExp) sheetExp.style.transform = 'none';
      if (sheetVerdict) sheetVerdict.style.transform = 'none';
      if (ring) ring.style.strokeDashoffset = '8';
      if (foldLabel) foldLabel.textContent = 'open';
      bars.forEach((b) => { b.style.width = b.dataset.target || '90%'; });
      return;
    }

    // 1. Scroll-scrubbed Resume Opening (scroll down) & Closing (scroll up)
    let targetProgress = 0;
    let currentProgress = 0;
    let rafId = null;

    function computeScrollProgress() {
      const maxScroll = window.innerWidth < 768 ? 260 : 340;
      const y = Math.max(0, window.scrollY || window.pageYOffset || 0);
      return Math.min(1, y / maxScroll);
    }

    function applyResumeFold(p) {
      // Smooth eased progress
      const ease = p * (2 - p);
      // Sheet 2 unfolds from -68deg -> 0deg
      if (sheetExp) {
        const rot2 = -68 * (1 - ease);
        const ty2 = -18 * (1 - ease);
        const sc2 = 0.94 + 0.06 * ease;
        sheetExp.style.transform = `rotateX(${rot2.toFixed(2)}deg) translateY(${ty2.toFixed(1)}px) scale(${sc2.toFixed(3)})`;
        sheetExp.style.opacity = (0.38 + 0.62 * ease).toFixed(3);
      }
      // Sheet 3 unfolds from -82deg -> 0deg (slightly delayed)
      const p3 = Math.max(0, Math.min(1, (p - 0.15) / 0.85));
      const ease3 = p3 * (2 - p3);
      if (sheetVerdict) {
        const rot3 = -82 * (1 - ease3);
        const ty3 = -28 * (1 - ease3);
        const sc3 = 0.9 + 0.1 * ease3;
        sheetVerdict.style.transform = `rotateX(${rot3.toFixed(2)}deg) translateY(${ty3.toFixed(1)}px) scale(${sc3.toFixed(3)})`;
        sheetVerdict.style.opacity = (0.25 + 0.75 * ease3).toFixed(3);
      }
      if (ring) {
        const dash = 45 - 37 * ease; // 45 -> 8 (92%)
        ring.style.strokeDashoffset = dash.toFixed(1);
      }
      if (scoreEl) {
        const val = Math.round(55 + 37 * ease);
        scoreEl.textContent = `${val}%`;
      }
      if (foldLabel) {
        foldLabel.textContent = p > 0.65 ? 'open' : p > 0.12 ? 'opening' : 'folded';
      }
      bars.forEach((bar, idx) => {
        const target = parseFloat(bar.dataset.target || '90');
        const base = idx === 0 ? 45 : 30;
        const w = base + (target - base) * ease;
        bar.style.width = `${w.toFixed(1)}%`;
      });
    }

    function tick() {
      currentProgress += (targetProgress - currentProgress) * 0.14;
      if (Math.abs(targetProgress - currentProgress) < 0.002) {
        currentProgress = targetProgress;
        applyResumeFold(currentProgress);
        rafId = null;
        return;
      }
      applyResumeFold(currentProgress);
      rafId = window.requestAnimationFrame(tick);
    }

    function onScroll() {
      targetProgress = computeScrollProgress();
      if (!rafId) {
        rafId = window.requestAnimationFrame(tick);
      }
    }

    if (stage) {
      targetProgress = computeScrollProgress();
      currentProgress = targetProgress;
      applyResumeFold(currentProgress);
      window.addEventListener('scroll', onScroll, { passive: true });
      window.addEventListener('resize', onScroll, { passive: true });
    }

    // 2. Subtle Anime.js scroll stagger on lower capability & feature cards
    const animeApi = window.anime;
    const grids = document.querySelectorAll('.capabilities-grid-3, .capabilities-grid-2, .feature-grid-3');
    if (animeApi && typeof animeApi.animate === 'function' && 'IntersectionObserver' in window && grids.length) {
      const { animate, stagger } = animeApi;
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            const cards = entry.target.querySelectorAll('.clean-card, .feature-card-detailed');
            if (cards.length) {
              animate(cards, {
                translateY: [14, 0],
                duration: 500,
                delay: stagger(65),
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
