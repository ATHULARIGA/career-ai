/**
 * Responsive scroll-driven 3D fold/unfold ("opening & closing") animation
 * across the entire ResuMate landing page.
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

    const foldItems = Array.from(
      document.querySelectorAll(
        '.skill-pills-wrap, .capabilities-heading-wrap, .clean-card, .feature-card-detailed, .how-heading-col, .step-row-item, .faq-item, .clean-banner'
      )
    ).map((el, idx) => ({
      el,
      staggerOffset: (idx % 3) * 0.08,
      current: 0,
      target: 0,
      visible: true,
    }));

    const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reducedMotion) {
      if (sheetExp) sheetExp.style.transform = 'none';
      if (sheetVerdict) sheetVerdict.style.transform = 'none';
      if (ring) ring.style.strokeDashoffset = '8';
      if (foldLabel) foldLabel.textContent = 'open';
      bars.forEach((b) => { b.style.width = b.dataset.target || '90%'; });
      foldItems.forEach(({ el }) => {
        el.style.transform = 'none';
        el.style.opacity = '1';
      });
      return;
    }

    let targetHero = 0;
    let currentHero = 0;
    let rafId = null;
    let lastTime = 0;
    let needsMeasure = false;

    function computeHeroProgress() {
      const maxScroll = window.innerWidth < 768 ? 240 : 320;
      const y = Math.max(0, window.scrollY || window.pageYOffset || 0);
      return Math.min(1, y / maxScroll);
    }

    function applyHeroFold(p) {
      const ease = p * (2 - p);
      if (sheetExp) {
        const rot2 = -68 * (1 - ease);
        const ty2 = -18 * (1 - ease);
        const sc2 = 0.94 + 0.06 * ease;
        sheetExp.style.transform = `rotateX(${rot2.toFixed(2)}deg) translateY(${ty2.toFixed(1)}px) scale(${sc2.toFixed(3)})`;
        sheetExp.style.opacity = (0.38 + 0.62 * ease).toFixed(3);
      }
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
        ring.style.strokeDashoffset = (45 - 37 * ease).toFixed(1);
      }
      if (scoreEl) {
        scoreEl.textContent = `${Math.round(55 + 37 * ease)}%`;
      }
      if (foldLabel) {
        foldLabel.textContent = p > 0.65 ? 'open' : p > 0.12 ? 'opening' : 'folded';
      }
      bars.forEach((bar, idx) => {
        const target = parseFloat(bar.dataset.target || '90');
        const base = idx === 0 ? 45 : 30;
        bar.style.width = `${(base + (target - base) * ease).toFixed(1)}%`;
      });
    }

    const itemByEl = new Map(foldItems.map((item) => [item.el, item]));
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            const item = itemByEl.get(entry.target);
            if (!item) return;
            item.visible = entry.isIntersecting;
            if (!entry.isIntersecting) {
              item.target = entry.boundingClientRect.top < 0 ? 1 : 0;
              if (!rafId && item.current !== item.target) {
                rafId = window.requestAnimationFrame(tick);
              }
            }
          });
        },
        { rootMargin: '120px 0px 120px 0px' }
      );
      foldItems.forEach((item) => {
        item.visible = false;
        io.observe(item.el);
      });
    }

    function computeItemTargets() {
      const vh = window.innerHeight || 800;
      const startY = vh * 0.98;
      const endY = vh * 0.48;
      const span = Math.max(160, startY - endY);

      foldItems.forEach((item) => {
        if (!item.visible) return;
        const rect = item.el.getBoundingClientRect();
        const raw = (startY - rect.top) / span - item.staggerOffset;
        item.target = Math.max(0, Math.min(1, raw));
      });
    }

    function applyItemFold(item) {
      if (item.current >= 1) {
        item.el.style.transform = 'none';
        item.el.style.opacity = '1';
        item.el.style.willChange = 'auto';
        return;
      }
      const t = item.current;
      const ease = t * t * (3 - 2 * t);
      const rot = -38 * (1 - ease);
      const ty = 36 * (1 - ease);
      const sc = 0.91 + 0.09 * ease;
      item.el.style.willChange = item.current !== item.target ? 'transform, opacity' : 'auto';
      item.el.style.transform = `rotateX(${rot.toFixed(2)}deg) translateY(${ty.toFixed(1)}px) scale(${sc.toFixed(3)})`;
      item.el.style.opacity = (0.22 + 0.78 * ease).toFixed(3);
    }

    function tick(now) {
      const dt = lastTime ? Math.min(0.05, Math.max(0.004, (now - lastTime) / 1000)) : 1 / 60;
      lastTime = now;

      if (needsMeasure) {
        if (manualHeroFold === null) {
          targetHero = computeHeroProgress();
        }
        computeItemTargets();
        needsMeasure = false;
      }

      const heroAlpha = 1 - Math.exp(-8.5 * dt);
      const itemAlpha = 1 - Math.exp(-7.5 * dt);
      let moving = false;

      if (stage && currentHero !== targetHero) {
        currentHero += (targetHero - currentHero) * heroAlpha;
        if (Math.abs(targetHero - currentHero) < 0.0015) {
          currentHero = targetHero;
        } else {
          moving = true;
        }
        applyHeroFold(currentHero);
      }

      foldItems.forEach((item) => {
        if (item.current === item.target) return;
        item.current += (item.target - item.current) * itemAlpha;
        if (Math.abs(item.target - item.current) < 0.002) {
          item.current = item.target;
        } else {
          moving = true;
        }
        applyItemFold(item);
      });

      if (moving || needsMeasure) {
        rafId = window.requestAnimationFrame(tick);
      } else {
        rafId = null;
        lastTime = 0;
      }
    }

    let manualHeroFold = null;

    function toggleHeroStage() {
      if (!stage) return;
      manualHeroFold = currentHero < 0.5 ? 1 : 0;
      targetHero = manualHeroFold;
      stage.setAttribute('aria-expanded', manualHeroFold === 1 ? 'true' : 'false');
      if (!rafId) {
        lastTime = performance.now();
        rafId = window.requestAnimationFrame(tick);
      }
    }

    if (stage) {
      stage.addEventListener('click', toggleHeroStage);
      stage.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          toggleHeroStage();
        }
      });
    }

    function onScroll() {
      manualHeroFold = null;
      needsMeasure = true;
      if (!rafId) {
        lastTime = performance.now();
        rafId = window.requestAnimationFrame(tick);
      }
    }

    targetHero = computeHeroProgress();
    currentHero = targetHero;
    if (stage) applyHeroFold(currentHero);

    const vhInit = window.innerHeight || 800;
    const startInit = vhInit * 0.98;
    const spanInit = Math.max(160, startInit - vhInit * 0.48);
    foldItems.forEach((item) => {
      const rect = item.el.getBoundingClientRect();
      const raw = (startInit - rect.top) / spanInit - item.staggerOffset;
      item.target = Math.max(0, Math.min(1, raw));
      item.current = item.target;
      applyItemFold(item);
    });

    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHomeMotion);
  } else {
    initHomeMotion();
  }
})();
