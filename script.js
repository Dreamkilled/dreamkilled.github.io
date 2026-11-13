(() => {
  "use strict";

  const lightbox = document.getElementById("lightbox");
  const lightboxImage = lightbox?.querySelector(".lightbox__image");
  const lightboxCaption = lightbox?.querySelector(".lightbox__caption");
  const lightboxCounter = lightbox?.querySelector(".lightbox__counter");
  const closeButton = lightbox?.querySelector(".lightbox__close");
  const prevButton = lightbox?.querySelector(".lightbox__arrow--prev");
  const nextButton = lightbox?.querySelector(".lightbox__arrow--next");

  const photoTriggers = Array.from(
    document.querySelectorAll(".photo-button[data-full]")
  );
  let activePhotos = [];
  let currentIndex = -1;
  let lastFocused = null;

  const setHidden = (element, hidden) => {
    if (element) element.hidden = hidden;
  };

  function updateLightbox(index) {
    if (!lightboxImage || index < 0 || index >= activePhotos.length) return;
    currentIndex = index;
    const photo = activePhotos[index];
    lightboxImage.src = photo.dataset.full || "";
    lightboxImage.alt = photo.querySelector("img")?.alt || "";

    if (lightboxCaption) {
      const caption = (photo.dataset.caption || "").trim();
      lightboxCaption.textContent = caption;
      lightboxCaption.hidden = !caption;
    }

    if (lightboxCounter) {
      lightboxCounter.textContent = `${index + 1} / ${activePhotos.length}`;
      lightboxCounter.hidden = activePhotos.length < 2;
    }

    const multiple = activePhotos.length > 1;
    setHidden(prevButton, !multiple);
    setHidden(nextButton, !multiple);
  }

  function openLightbox(trigger) {
    if (!lightbox) return;
    const carousel = trigger.closest(".carousel");
    activePhotos = carousel
      ? Array.from(
          carousel.querySelectorAll(".photo-button[data-full]")
        )
      : [trigger];
    const index = activePhotos.indexOf(trigger);
    lastFocused = trigger || document.activeElement;
    updateLightbox(index < 0 ? 0 : index);
    lightbox.classList.add("is-open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("lightbox-open");
    closeButton?.focus();
  }

  function closeLightbox() {
    if (!lightbox) return;
    lightbox.classList.remove("is-open");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("lightbox-open");
    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus();
    }
    lastFocused = null;
  }

  function stepLightbox(delta) {
    if (!activePhotos.length) return;
    updateLightbox(
      (currentIndex + delta + activePhotos.length) % activePhotos.length
    );
  }

  if (lightbox) {
    photoTriggers.forEach((photo) => {
      photo.addEventListener("click", (event) => {
        event.preventDefault();
        openLightbox(photo);
      });
    });

    closeButton?.addEventListener("click", closeLightbox);
    prevButton?.addEventListener("click", () => stepLightbox(-1));
    nextButton?.addEventListener("click", () => stepLightbox(1));

    let lightboxSwiped = false;

    lightbox.addEventListener("click", (event) => {
      if (lightboxSwiped) {
        lightboxSwiped = false;
        return;
      }
      if (event.target === lightbox) closeLightbox();
    });

    document.addEventListener("keydown", (event) => {
      if (!lightbox.classList.contains("is-open")) return;

      if (event.key === "Escape") {
        event.preventDefault();
        closeLightbox();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        stepLightbox(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        stepLightbox(1);
      } else if (event.key === "Tab") {
        trapFocus(event);
      }
    });

    let touchStartX = null;
    let touchStartY = null;

    lightbox.addEventListener(
      "touchstart",
      (event) => {
        if (event.touches.length !== 1) return;
        touchStartX = event.touches[0].clientX;
        touchStartY = event.touches[0].clientY;
      },
      { passive: true }
    );

    lightbox.addEventListener(
      "touchend",
      (event) => {
        if (touchStartX === null || event.changedTouches.length !== 1) {
          return;
        }
        const dx = event.changedTouches[0].clientX - touchStartX;
        const dy = event.changedTouches[0].clientY - touchStartY;
        touchStartX = null;
        touchStartY = null;

        if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy)) return;
        lightboxSwiped = true;
        window.setTimeout(() => {
          lightboxSwiped = false;
        }, 400);
        stepLightbox(dx < 0 ? 1 : -1);
      },
      { passive: true }
    );

    function trapFocus(event) {
      const focusable = [closeButton, prevButton, nextButton].filter(
        (element) => element && !element.hidden
      );
      if (!focusable.length) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }

  document.querySelectorAll(".carousel").forEach((carousel) => {
    const track = carousel.querySelector(".carousel__track");
    const slides = Array.from(
      carousel.querySelectorAll(".carousel__slide")
    );
    const prev = carousel.querySelector(".carousel__arrow--prev");
    const next = carousel.querySelector(".carousel__arrow--next");
    const counter = carousel.querySelector(".carousel__counter");
    const viewport = carousel.querySelector(".carousel__viewport");
    const caption = carousel
      .closest("figure")
      ?.querySelector(".carousel__caption");

    if (!track || slides.length < 2) return;

    let index = 0;

    function update() {
      track.style.transform = `translateX(-${index * 100}%)`;
      if (counter) {
        counter.textContent = `${index + 1}/${slides.length}`;
      }
      if (caption) {
        const captionHtml = (slides[index].dataset.captionHtml || "").trim();
        const captionText = (slides[index].dataset.caption || "").trim();
        if (captionHtml) {
          caption.innerHTML = captionHtml;
          caption.hidden = false;
        } else {
          caption.textContent = captionText;
          caption.hidden = !captionText;
        }
      }
      slides.forEach((slide, slideIndex) => {
        const active = slideIndex === index;
        slide.setAttribute("aria-hidden", active ? "false" : "true");
        slide.tabIndex = active ? 0 : -1;
      });
    }

    function go(delta) {
      index = (index + delta + slides.length) % slides.length;
      update();
    }

    prev?.addEventListener("click", () => go(-1));
    next?.addEventListener("click", () => go(1));

    carousel.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        go(-1);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        go(1);
      }
    });

    if (viewport) {
      let startX = null;
      let startY = null;
      let swiped = false;
      let resetTimer = null;

      viewport.addEventListener(
        "touchstart",
        (event) => {
          if (event.touches.length !== 1) return;
          startX = event.touches[0].clientX;
          startY = event.touches[0].clientY;
          swiped = false;
        },
        { passive: true }
      );

      viewport.addEventListener(
        "touchend",
        (event) => {
          if (startX === null || event.changedTouches.length !== 1) {
            return;
          }
          const dx = event.changedTouches[0].clientX - startX;
          const dy = event.changedTouches[0].clientY - startY;
          startX = null;
          startY = null;

          if (Math.abs(dx) < 50 || Math.abs(dx) < Math.abs(dy)) return;

          swiped = true;
          window.clearTimeout(resetTimer);
          resetTimer = window.setTimeout(() => {
            swiped = false;
          }, 400);
          go(dx < 0 ? 1 : -1);
        },
        { passive: true }
      );

      viewport.addEventListener(
        "click",
        (event) => {
          if (!swiped) return;
          event.preventDefault();
          event.stopPropagation();
          swiped = false;
        },
        true
      );
    }

    update();
  });

  const searchRoot = document.querySelector(".site-search");
  const searchInput = searchRoot?.querySelector(".site-search__input");
  const searchResults = searchRoot?.querySelector(
    ".site-search__results"
  );

  if (searchRoot && searchInput && searchResults) {
    const searchLang =
      searchRoot.dataset.searchLang === "en" ? "en" : "ru";
    const searchIndexUrl =
      searchRoot.dataset.searchIndex || "/search-index.json";
    const emptyLabel =
      searchLang === "en" ? "No games found" : "Ничего не найдено";
    const unavailableLabel =
      searchLang === "en"
        ? "Search is temporarily unavailable"
        : "Поиск временно недоступен";
    const collator = new Intl.Collator(searchLang, {
      sensitivity: "base",
      numeric: true,
    });
    let searchItems = [];
    let searchIndexPromise = null;
    let searchIndexFailed = false;
    let searchRequestId = 0;
    let activeIndex = -1;
    let visibleItems = [];

    function normalizeSearch(value) {
      return String(value || "")
        .toLocaleLowerCase(searchLang === "ru" ? "ru-RU" : "en-US")
        .replace(/ё/g, "е")
        .replace(/\s+/g, " ")
        .trim();
    }

    function localizedItemTitle(item) {
      return searchLang === "en"
        ? item.titleEn || item.titleRu || ""
        : item.titleRu || item.titleEn || "";
    }

    function localizedItemArticle(item) {
      return searchLang === "en"
        ? item.articleEn || item.articleRu || ""
        : item.articleRu || item.articleEn || "";
    }

    function localizedItemHref(item) {
      return searchLang === "en"
        ? item.hrefEn || item.hrefRu || ""
        : item.hrefRu || item.hrefEn || "";
    }

    function loadSearchIndex() {
      if (!searchIndexPromise) {
        searchIndexPromise = fetch(searchIndexUrl)
          .then((response) => {
            if (!response.ok) {
              throw new Error(`HTTP ${response.status}`);
            }
            return response.json();
          })
          .then((data) => {
            searchItems = Array.isArray(data) ? data : [];
            return searchItems;
          })
          .catch(() => {
            searchIndexFailed = true;
            searchItems = [];
            return searchItems;
          });
      }
      return searchIndexPromise;
    }

    function scoreItem(item, query) {
      const titleRu = normalizeSearch(item.titleRu);
      const titleEn = normalizeSearch(item.titleEn);
      const tokens = query.split(" ").filter(Boolean);
      const haystack = `${titleRu} ${titleEn}`;
      if (!tokens.every((token) => haystack.includes(token))) {
        return -1;
      }

      const primary = normalizeSearch(localizedItemTitle(item));
      if (primary === query) return 0;
      if (primary.startsWith(query)) return 1;

      const words = primary.split(/[^\p{L}\p{N}]+/u);
      if (words.some((word) => word.startsWith(query))) return 2;
      return 3;
    }

    function findMatches(query) {
      return searchItems
        .map((item) => ({ item, score: scoreItem(item, query) }))
        .filter((entry) => entry.score >= 0)
        .sort(
          (a, b) =>
            a.score - b.score ||
            collator.compare(
              localizedItemTitle(a.item),
              localizedItemTitle(b.item)
            )
        )
        .slice(0, 8)
        .map((entry) => entry.item);
    }

    function setSearchExpanded(expanded) {
      searchInput.setAttribute("aria-expanded", String(expanded));
    }

    function clearActive() {
      activeIndex = -1;
      searchInput.removeAttribute("aria-activedescendant");
      searchResults
        .querySelectorAll(".site-search__result")
        .forEach((option) => {
          option.classList.remove("is-active");
          option.setAttribute("aria-selected", "false");
        });
    }

    function closeSearchResults() {
      searchResults.hidden = true;
      searchResults.textContent = "";
      visibleItems = [];
      clearActive();
      setSearchExpanded(false);
    }

    function showSearchMessage(message) {
      searchResults.textContent = "";
      const status = document.createElement("div");
      status.className = "site-search__empty";
      status.setAttribute("role", "status");
      status.textContent = message;
      searchResults.append(status);
      searchResults.hidden = false;
      visibleItems = [];
      clearActive();
      setSearchExpanded(true);
    }

    function renderSearchResults(items) {
      searchResults.textContent = "";
      visibleItems = items;
      clearActive();

      if (!items.length) {
        showSearchMessage(
          searchIndexFailed ? unavailableLabel : emptyLabel
        );
        return;
      }

      items.forEach((item, index) => {
        const link = document.createElement("a");
        link.className = "site-search__result";
        link.id = `site-search-option-${index}`;
        link.href = localizedItemHref(item);
        link.tabIndex = -1;
        link.setAttribute("role", "option");
        link.setAttribute("aria-selected", "false");

        const title = document.createElement("span");
        title.className = "site-search__title";
        title.textContent = localizedItemTitle(item);

        const meta = document.createElement("span");
        meta.className = "site-search__meta";
        meta.textContent = localizedItemArticle(item);

        link.append(title, meta);
        searchResults.append(link);
      });

      searchResults.hidden = false;
      setSearchExpanded(true);
    }

    function setActiveResult(index) {
      const options = Array.from(
        searchResults.querySelectorAll(".site-search__result")
      );
      if (!options.length) return;

      if (index < 0) index = options.length - 1;
      if (index >= options.length) index = 0;
      activeIndex = index;

      options.forEach((option, optionIndex) => {
        const active = optionIndex === activeIndex;
        option.classList.toggle("is-active", active);
        option.setAttribute("aria-selected", String(active));
      });

      const activeOption = options[activeIndex];
      searchInput.setAttribute(
        "aria-activedescendant",
        activeOption.id
      );
      activeOption.scrollIntoView({ block: "nearest" });
    }

    async function runSearch() {
      const query = normalizeSearch(searchInput.value);
      if (!query) {
        closeSearchResults();
        return;
      }

      const requestId = ++searchRequestId;
      await loadSearchIndex();
      if (requestId !== searchRequestId) return;
      renderSearchResults(findMatches(query));
    }

    searchInput.addEventListener("input", () => {
      runSearch();
    });

    searchInput.addEventListener("focus", () => {
      if (normalizeSearch(searchInput.value)) runSearch();
    });

    searchInput.addEventListener("keydown", (event) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        if (searchResults.hidden) {
          runSearch().then(() => {
            if (!searchResults.hidden && visibleItems.length) {
              setActiveResult(0);
            }
          });
          return;
        }
        setActiveResult(activeIndex + 1);
      } else if (event.key === "ArrowUp") {
        if (searchResults.hidden || !visibleItems.length) return;
        event.preventDefault();
        setActiveResult(
          activeIndex < 0 ? visibleItems.length - 1 : activeIndex - 1
        );
      } else if (event.key === "Enter") {
        if (searchResults.hidden || !visibleItems.length) return;
        event.preventDefault();
        const index = activeIndex < 0 ? 0 : activeIndex;
        const href = localizedItemHref(visibleItems[index]);
        if (href) window.location.assign(href);
      } else if (event.key === "Escape") {
        if (!searchResults.hidden) {
          event.preventDefault();
          closeSearchResults();
        }
      }
    });

    document.addEventListener(
      "keydown",
      (event) => {
        if (event.ctrlKey || event.metaKey || event.altKey) return;

        const slashKey =
          event.key === "/" ||
          (!event.shiftKey &&
            ["Slash", "Backslash", "NumpadDivide"].includes(event.code));
        if (!slashKey) return;
        if (document.body.classList.contains("lightbox-open")) return;

        const target = event.target;
        if (target instanceof HTMLElement) {
          if (target.isContentEditable) return;
          if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
            return;
          }
        }

        event.preventDefault();
        searchInput.focus();
      },
      true
    );

    searchRoot.addEventListener("focusout", () => {
      window.setTimeout(() => {
        if (!searchRoot.contains(document.activeElement)) {
          closeSearchResults();
        }
      }, 0);
    });

    document.addEventListener("pointerdown", (event) => {
      if (!searchRoot.contains(event.target)) {
        closeSearchResults();
      }
    });
  }
})();
