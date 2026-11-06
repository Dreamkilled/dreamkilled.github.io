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

    if (!track || slides.length < 2) return;

    let index = 0;

    function update() {
      track.style.transform = `translateX(-${index * 100}%)`;
      if (counter) {
        counter.textContent = `${index + 1}/${slides.length}`;
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
})();
