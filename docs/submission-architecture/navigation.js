(() => {
  "use strict";

  const STARTUP_ID = decodeURIComponent(
    (window.__submissionArchitectureStartupHash || window.location.hash).replace(/^#\/?/, ""),
  );

  const SECTION_TITLES = [
    "High-Level Architecture",
    "State Extraction",
    "Retrieval",
    "Bi-Encoder",
    "Ranking",
    "Response Generation",
    "Examples",
    "Label Audit",
    "References",
  ];

  function init() {
    const deck = window.Reveal;
    if (!deck || document.documentElement.dataset.submissionDeckReady === "true") return;

    document.documentElement.dataset.submissionDeckReady = "true";

    const configureMobileCanvas = () => {
      if (window.matchMedia("(max-width: 760px)").matches) {
        deck.configure({
          width: window.innerWidth,
          height: window.innerHeight,
          margin: 0.02,
        });
      }
    };
    configureMobileCanvas();
    window.addEventListener("resize", configureMobileCanvas, {passive: true});

    const coordinatesForId = id => {
      const target = document.getElementById(id);
      const slides = document.querySelector(".reveal .slides");
      if (!target || !slides) return null;
      const horizontalSlides = [...slides.children].filter(node => node.tagName === "SECTION");
      const h = horizontalSlides.findIndex(node => node === target || node.contains(target));
      if (h < 0) return null;
      const verticalSlides = [...horizontalSlides[h].children].filter(node => node.tagName === "SECTION");
      const v = verticalSlides.length ? Math.max(0, verticalSlides.indexOf(target)) : 0;
      return {h, v};
    };

    const navigateToId = id => {
      const target = document.getElementById(id);
      if (!target) return false;
      if (deck.isScrollView()) {
        target.scrollIntoView({behavior: "auto", block: "start"});
        return true;
      }
      const coordinates = coordinatesForId(id);
      if (!coordinates) return false;
      deck.slide(coordinates.h, coordinates.v);
      return true;
    };

    const idFromHash = () => decodeURIComponent(window.location.hash.replace(/^#\/?/, ""));
    const resolveNamedHash = () => {
      const id = idFromHash();
      if (id && !/^\d+(?:\/\d+)?$/.test(id)) navigateToId(id);
    };

    document.addEventListener("click", event => {
      const link = event.target.closest?.('a[href^="#/"]');
      if (!link) return;
      const id = decodeURIComponent(link.getAttribute("href").replace(/^#\//, ""));
      if (navigateToId(id)) event.preventDefault();
    }, true);

    window.addEventListener("hashchange", () => requestAnimationFrame(resolveNamedHash));
    const rail = document.createElement("nav");
    rail.className = "deck-section-rail";
    rail.setAttribute("aria-label", "Deck sections");

    const buttons = SECTION_TITLES.map((title, index) => {
      const button = document.createElement("button");
      button.className = "deck-rail-button";
      button.type = "button";
      button.dataset.horizontalIndex = String(index + 1);
      button.setAttribute("aria-label", `${index + 1}. ${title}`);
      button.innerHTML = `<span class="deck-rail-number">${index + 1}</span><span class="deck-rail-label">${title}</span>`;
      button.addEventListener("click", () => {
        const current = deck.getIndices().h;
        if (current === index + 1) {
          deck.getPlugin("menu")?.openMenu();
          return;
        }
        deck.slide(index + 1, 0);
        button.focus({preventScroll: true});
      });
      rail.append(button);
      return button;
    });

    const themeButton = document.createElement("button");
    themeButton.className = "deck-theme-toggle";
    themeButton.type = "button";

    const storedTheme = localStorage.getItem("submission-deck-theme");
    const initialTheme = storedTheme === "light" ? "light" : "dark";
    const setTheme = theme => {
      document.documentElement.dataset.deckTheme = theme;
      themeButton.textContent = theme === "dark" ? "Light theme" : "Dark theme";
      themeButton.setAttribute("aria-label", `Switch to ${theme === "dark" ? "light" : "dark"} theme`);
      localStorage.setItem("submission-deck-theme", theme);
    };
    setTheme(initialTheme);
    themeButton.addEventListener("click", () => {
      setTheme(document.documentElement.dataset.deckTheme === "dark" ? "light" : "dark");
    });

    const position = document.createElement("div");
    position.className = "deck-position";
    position.setAttribute("aria-live", "polite");

    document.body.append(rail, themeButton, position);

    const update = event => {
      const indices = event?.indexh === undefined ? deck.getIndices() : {h: event.indexh, v: event.indexv};
      buttons.forEach((button, index) => {
        if (index + 1 === indices.h) button.setAttribute("aria-current", "true");
        else button.removeAttribute("aria-current");
      });
      const title = indices.h === 0 ? "Music-CRS Submission Architecture" : SECTION_TITLES[indices.h - 1];
      position.textContent = indices.h === 0 ? title : `${indices.h}.${indices.v} · ${title}`;
    };

    deck.on("slidechanged", update);
    deck.on("ready", event => {
      requestAnimationFrame(() => {
        if (STARTUP_ID && !/^\d+(?:\/\d+)?$/.test(STARTUP_ID)) navigateToId(STARTUP_ID);
        else resolveNamedHash();
      });
      update(event);
    });
    update();
    if (deck.isReady()) {
      requestAnimationFrame(() => {
        if (STARTUP_ID && !/^\d+(?:\/\d+)?$/.test(STARTUP_ID)) navigateToId(STARTUP_ID);
        else resolveNamedHash();
      });
    }

    window.__submissionArchitectureDeck = {
      openMenu: () => deck.getPlugin("menu")?.openMenu(),
      setTheme,
      goTo: (horizontal, vertical = 0) => deck.slide(horizontal, vertical),
      goToId: navigateToId,
      current: () => deck.getIndices(),
    };
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, {once: true});
  else init();
})();
