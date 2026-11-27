/**
 * Anime.js v4 interactive stagger grid, looping telemetry timeline,
 * and scroll/hover micro-interactions for the ResuMate landing page.
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
    const { animate, createTimeline, stagger } = animeApi;

    // 1. Signature Anime.js 10x6 Interactive Stagger Grid
    const gridEl = document.getElementById('heroStaggerGrid');
    const COLS = 10;
    const ROWS = 6;
    if (gridEl) {
      const frag = document.createDocumentFragment();
      for (let i = 0; i < COLS * ROWS; i += 1) {
        const dot = document.createElement('span');
        dot.className = 'hero-grid-dot';
        dot.dataset.index = String(i);
        frag.appendChild(dot);
      }
      gridEl.appendChild(frag);

      const dots = gridEl.querySelectorAll('.hero-grid-dot');
      let autoRipple = null;

      function runGridWave(fromTarget) {
        if (autoRipple && typeof autoRipple.pause === 'function') {
          autoRipple.pause();
        }
        autoRipple = createTimeline({
          loop: true,
          defaults: { ease: 'inOutSine' },
        })
          .add(dots, {
            scale: [
              { to: 1.55, duration: 360 },
              { to: 0.75, duration: 480 },
              { to: 1, duration: 420 },
            ],
            opacity: [
              { to: 1, duration: 360 },
              { to: 0.35, duration: 480 },
              { to: 0.65, duration: 420 },
            ],
            delay: stagger(45, { grid: [COLS, ROWS], from: fromTarget }),
          })
          .add(dots, {
            scale: 1,
            duration: 600,
          });
      }

      runGridWave('center');

      gridEl.addEventListener('click', (e) => {
        const target = e.target.closest('.hero-grid-dot');
        if (!target) return;
        const idx = Number(target.dataset.index || 0);
        runGridWave(idx);
      });

      gridEl.addEventListener('mouseover', (e) => {
        const target = e.target.closest('.hero-grid-dot');
        if (!target) return;
        animate(target, {
          scale: [1, 1.8, 1],
          duration: 500,
          ease: 'outElastic(1, .6)',
        });
      });
    }

    // 2. Looping Live Telemetry Timeline (ring, bars, live indicator)
    const liveDot = document.querySelector('.telemetry-live-dot');
    if (liveDot) {
      animate(liveDot, {
        scale: [1, 1.45, 1],
        opacity: [1, 0.45, 1],
        duration: 1400,
        loop: true,
        ease: 'inOutSine',
      });
    }

    const ring = document.querySelector('.hero-telemetry-ring');
    const scoreEl = document.querySelector('.telemetry-score-num');
    const bars = document.querySelectorAll('.telemetry-bar-fill');

    if (ring || bars.length) {
      const tl = createTimeline({
        loop: true,
        defaults: { ease: 'outExpo' },
      });

      if (ring) {
        tl.add(ring, {
          strokeDashoffset: [100, 8],
          duration: 1200,
        }, 0);
      }
      if (scoreEl) {
        const counter = { val: 0 };
        tl.add(counter, {
          val: 92,
          duration: 1100,
          onUpdate: () => {
            scoreEl.textContent = `${Math.round(counter.val)}%`;
          },
        }, 0);
      }
      if (bars.length) {
        tl.add(bars, {
          width: ['12%', (el) => el.dataset.target || '88%'],
          duration: 1000,
          delay: stagger(140),
        }, 120);
        tl.add(bars, {
          opacity: [1, 0.72, 1],
          duration: 1600,
          delay: stagger(120),
        });
      }
    }

    // 3. Scroll-triggered stagger on capability & feature grids
    const grids = document.querySelectorAll('.capabilities-grid-3, .capabilities-grid-2, .feature-grid-3');
    if ('IntersectionObserver' in window && grids.length) {
      const observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            const cards = entry.target.querySelectorAll('.clean-card, .feature-card-detailed');
            if (cards.length) {
              animate(cards, {
                translateY: [18, 0],
                scale: [0.97, 1],
                duration: 600,
                delay: stagger(80),
                ease: 'outBack(1.4)',
              });
            }
            observer.unobserve(entry.target);
          });
        },
        { threshold: 0.12 }
      );
      grids.forEach((grid) => observer.observe(grid));
    }

    // 4. Hover spring lift on skill pills
    document.querySelectorAll('.skill-pill').forEach((pill) => {
      pill.addEventListener('mouseenter', () => {
        animate(pill, { translateY: -3, scale: 1.04, duration: 240, ease: 'outQuad' });
      });
      pill.addEventListener('mouseleave', () => {
        animate(pill, { translateY: 0, scale: 1, duration: 240, ease: 'outQuad' });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHomeMotion);
  } else {
    initHomeMotion();
  }
})();
