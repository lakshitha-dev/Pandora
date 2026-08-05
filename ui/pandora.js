/* ============================================================================
   PANDORA — LIVE BACKGROUND
   The bioluminescent ambience, owned in one place so every page gets the same
   thing. Styles live in pandora.css (.ambient / .plankton); this module owns the
   markup, the particle count, and the lifecycle.

   Load with: <script src="pandora.js" defer></script>

   Idempotent — if a page already ships its own .ambient or populated .plankton,
   that markup is left alone rather than duplicated.
   ========================================================================== */
(() => {
  "use strict";

  const reduced = matchMedia("(prefers-reduced-motion: reduce)");

  /**
   * Particle count scaled to viewport area rather than fixed.
   *
   * A fixed count that reads well at 1440×900 looks sparse on a 4K display and
   * crowded on a laptop. Area-derived keeps the apparent density constant.
   * Capped at 16 because every particle is a separately composited layer, and
   * demo hardware is unknown — dropped frames cost more than extra spores earn.
   */
  function particleCount() {
    const area = innerWidth * innerHeight;
    return Math.max(8, Math.min(16, Math.round(area / 120000)));
  }

  /** Insert an element as the first child of body, before page content. */
  function prepend(el) {
    document.body.insertBefore(el, document.body.firstChild);
  }

  function ensureAmbient() {
    if (document.querySelector(".ambient")) return;
    const el = document.createElement("div");
    el.className = "ambient";
    el.setAttribute("aria-hidden", "true");
    prepend(el);
  }

  function ensurePlankton() {
    // Reduced motion: no particles at all. The CSS hides the layer too, but not
    // creating them avoids the DOM cost for a user who will never see them.
    if (reduced.matches) return;

    let host = document.querySelector(".plankton");
    if (host && host.children.length) return; // page already populated it

    if (!host) {
      host = document.createElement("div");
      host.className = "plankton";
      host.setAttribute("aria-hidden", "true");
      prepend(host);
    }

    const frag = document.createDocumentFragment();
    for (let i = 0; i < particleCount(); i++) {
      const p = document.createElement("i");
      const size = (1.5 + Math.random() * 2.4).toFixed(1);
      p.style.cssText =
        `left:${(Math.random() * 100).toFixed(2)}vw;` +
        // Start below the fold and rise through; negative delay means the field
        // is already in motion on first paint instead of filling in from empty.
        `top:${(100 + Math.random() * 25).toFixed(0)}vh;` +
        `width:${size}px;height:${size}px;` +
        `animation-duration:${(20 + Math.random() * 20).toFixed(0)}s;` +
        `animation-delay:-${(Math.random() * 36).toFixed(0)}s;` +
        `opacity:${(0.26 + Math.random() * 0.42).toFixed(2)}`;
      frag.appendChild(p);
    }
    host.appendChild(frag);
  }

  function clearPlankton() {
    const host = document.querySelector(".plankton");
    if (host) host.replaceChildren();
  }

  /* --- Pause while the tab is hidden. A background tab animating two blurred
     gradients and a dozen particles burns battery for nobody's benefit, and on
     a demo laptop that heat budget is better spent on the foreground. --- */
  function bindVisibility() {
    document.addEventListener("visibilitychange", () => {
      document.body.classList.toggle("is-hidden", document.hidden);
    });
  }

  /* --- Re-density on resize, debounced. Rotating a tablet or moving a window
     between displays changes the area enough to matter. --- */
  function bindResize() {
    let t;
    addEventListener("resize", () => {
      clearTimeout(t);
      t = setTimeout(() => {
        if (reduced.matches) return;
        clearPlankton();
        ensurePlankton();
      }, 400);
    });
  }

  /* --- Honour a live change to the motion preference, not just the value at
     load. Someone toggling reduce-motion should see it take effect. --- */
  function bindMotionPreference() {
    const onChange = () => {
      if (reduced.matches) clearPlankton();
      else ensurePlankton();
    };
    reduced.addEventListener?.("change", onChange);
  }

  function init() {
    ensureAmbient();
    ensurePlankton();
    bindVisibility();
    bindResize();
    bindMotionPreference();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
