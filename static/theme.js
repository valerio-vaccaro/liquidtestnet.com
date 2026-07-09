(function () {
  "use strict";

  var nav = document.querySelector(".site-nav");
  var links = document.querySelector(".site-nav__links");
  var toggle = document.querySelector(".site-nav__toggle");

  if (toggle && links) {
    toggle.addEventListener("click", function () {
      var open = links.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  if (nav) {
    var onScroll = function () {
      nav.classList.toggle("is-scrolled", window.scrollY > 8);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  if (links) {
    var here = window.location.pathname.replace(/\/$/, "") || "/";
    Array.prototype.forEach.call(links.querySelectorAll("a"), function (a) {
      var path = a.getAttribute("href");
      if (!path || path.indexOf("http") === 0) return;
      path = path.replace(/\/$/, "") || "/";
      if (path === here) {
        a.classList.add("is-active");
      }
    });
  }

  // Mark panels/headings for scroll-reveal without touching every template.
  var revealTargets = document.querySelectorAll(".well, .container-fluid > #sl > h1, .container-fluid > #sl > h2");
  revealTargets.forEach(function (el) {
    el.classList.add("reveal");
  });

  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (reduceMotion || !("IntersectionObserver" in window)) {
    revealTargets.forEach(function (el) {
      el.classList.add("is-visible");
    });
    return;
  }

  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry, i) {
        if (entry.isIntersecting) {
          var el = entry.target;
          setTimeout(function () {
            el.classList.add("is-visible");
          }, i * 60);
          observer.unobserve(el);
        }
      });
    },
    { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
  );

  revealTargets.forEach(function (el) {
    observer.observe(el);
  });
})();
