(() => {
  const root = document.querySelector("[data-guide-page]");
  if (!root) return;

  const RETURN_DELAY_MS = 3000;
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  const mobileViewport = window.matchMedia?.("(max-width: 820px)");
  const toc = root.querySelector(".guide-toc");
  const list = root.querySelector("[data-guide-step-list]");
  const levelOutput = root.querySelector("[data-guide-context-level]");
  const timecodeButton = root.querySelector("[data-guide-context-timecode]");
  const video = root.querySelector("[data-guide-video]");
  const toggle = root.querySelector(".guide-toc-toggle");

  if (!toc || !list) return;

  const headings = Array.from(root.querySelectorAll("h3.guide-step[id]"));
  const links = Array.from(list.querySelectorAll("a[href*='#']"));

  if (!headings.length || !links.length) return;

  const prefersReducedMotion = () => reducedMotion?.matches === true;
  const isMobile = () => mobileViewport?.matches === true;

  const safeDecodeHash = (hash) => {
    const encodedId = hash.startsWith("#") ? hash.slice(1) : hash;
    try {
      return decodeURIComponent(encodedId);
    } catch {
      return encodedId;
    }
  };

  const linkTargetId = (link) => {
    try {
      return safeDecodeHash(new URL(link.href, window.location.href).hash);
    } catch {
      const href = link.getAttribute("href") || "";
      return safeDecodeHash(href.slice(href.indexOf("#")));
    }
  };

  const clockToSeconds = (clock) => {
    const parts = clock.trim().split(":");
    if (
      parts.length < 2
      || parts.length > 3
      || parts.some((part) => !/^\d+$/.test(part))
    ) {
      return null;
    }

    const values = parts.map(Number);
    if (values.at(-1) > 59 || (values.length === 3 && values.at(-2) > 59)) {
      return null;
    }

    return values.reduce((total, value) => total * 60 + value, 0);
  };

  const timecodeStart = (range) => {
    if (typeof range !== "string") return null;
    return clockToSeconds(range.split("–", 1)[0]);
  };

  const headingsById = new Map(headings.map((heading) => [heading.id, heading]));
  const headingByLink = new Map();
  const linkByHeading = new Map();

  links.forEach((link, index) => {
    const heading = headingsById.get(linkTargetId(link));
    if (heading) {
      headingByLink.set(link, heading);
      linkByHeading.set(heading, link);
    }

    const text = link.textContent.trim();
    link.textContent = "";
    link.dataset.guideIndex = String(index + 1).padStart(2, "0");
    const textElement = document.createElement("span");
    textElement.className = "guide-toc__link-text";
    textElement.textContent = text;
    link.append(textElement);
  });

  const trackedHeadings = headings.filter((heading) => linkByHeading.has(heading));
  if (!trackedHeadings.length) return;

  document.documentElement.classList.add("js");

  let activeLink = null;
  let manualTocNavigation = false;
  let returnTimer = null;
  let scheduled = false;

  const centerActiveLink = (behavior = "auto") => {
    if (!activeLink) return;

    const tocBounds = toc.getBoundingClientRect();
    const linkBounds = activeLink.getBoundingClientRect();
    const top = toc.scrollTop
      + linkBounds.top
      - tocBounds.top
      - (toc.clientHeight - linkBounds.height) / 2;

    toc.scrollTo({ top: Math.max(0, top), behavior });
  };

  const updateContext = (heading) => {
    if (levelOutput) levelOutput.textContent = heading.dataset.level || "—";
    if (!timecodeButton) return;

    const timecode = heading.dataset.timecode || "";
    const seconds = timecodeStart(timecode);
    timecodeButton.textContent = timecode || "—";

    if (Number.isFinite(seconds) && seconds >= 0) {
      timecodeButton.dataset.seconds = String(seconds);
      timecodeButton.disabled = false;
    } else {
      delete timecodeButton.dataset.seconds;
      timecodeButton.disabled = true;
    }
  };

  const setActiveLink = (nextLink) => {
    if (!nextLink) return;

    if (nextLink !== activeLink) {
      activeLink?.classList.remove("is-active");
      activeLink?.removeAttribute("aria-current");
      activeLink = nextLink;
      activeLink.classList.add("is-active");
      activeLink.setAttribute("aria-current", "location");
    }

    const heading = headingByLink.get(activeLink);
    if (!heading) return;
    updateContext(heading);

    if (!manualTocNavigation) centerActiveLink("auto");
  };

  const updateFromScroll = () => {
    const trackingLine = Math.min(180, window.innerHeight * 0.3);
    let current = trackedHeadings[0];

    for (const heading of trackedHeadings) {
      if (heading.getBoundingClientRect().top <= trackingLine) current = heading;
      else break;
    }

    setActiveLink(linkByHeading.get(current));
  };

  const requestScrollUpdate = () => {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      updateFromScroll();
    });
  };

  const cancelReturn = () => {
    window.clearTimeout(returnTimer);
    returnTimer = null;
  };

  const scheduleReturn = () => {
    cancelReturn();
    returnTimer = window.setTimeout(() => {
      returnTimer = null;
      if (toc.matches(":hover") || toc.contains(document.activeElement)) return;
      manualTocNavigation = false;
      centerActiveLink(prefersReducedMotion() ? "auto" : "smooth");
    }, RETURN_DELAY_MS);
  };

  const startManualNavigation = () => {
    manualTocNavigation = true;
    cancelReturn();
  };

  const setTocOpen = (open) => {
    toc.classList.toggle("is-open", open);
    if (!toggle) return;

    toggle.setAttribute("aria-expanded", String(open));
    const symbol = toggle.querySelector("[aria-hidden='true']");
    if (symbol) symbol.textContent = open ? "−" : "＋";
  };

  window.addEventListener("scroll", requestScrollUpdate, { passive: true });
  toc.addEventListener("pointerenter", startManualNavigation);
  toc.addEventListener("pointerdown", startManualNavigation);
  toc.addEventListener("pointerleave", scheduleReturn);
  toc.addEventListener("focusin", startManualNavigation);
  toc.addEventListener("focusout", scheduleReturn);

  if (timecodeButton) {
    timecodeButton.addEventListener("click", () => {
      const seconds = Number(timecodeButton.dataset.seconds);
      if (!Number.isFinite(seconds) || seconds < 0) return;

      video?.scrollIntoView({
        behavior: prefersReducedMotion() ? "auto" : "smooth",
        block: "center",
      });
      document.dispatchEvent(new CustomEvent("bdo-guide:seek-video", {
        detail: { seconds },
      }));
    });
  }

  if (toggle) {
    toggle.addEventListener("click", () => {
      setTocOpen(!toc.classList.contains("is-open"));
    });

    toggle.addEventListener("keydown", (event) => {
      if (event.key !== "Escape" || !toc.classList.contains("is-open")) return;
      event.preventDefault();
      setTocOpen(false);
    });
  }

  links.forEach((link) => {
    link.addEventListener("click", () => {
      if (isMobile()) setTocOpen(false);
    });
  });

  toc.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || !toc.classList.contains("is-open")) return;
    event.preventDefault();
    setTocOpen(false);
    toggle?.focus();
  });

  updateFromScroll();
})();
