(function () {
  var font = document.createElement("link");
  font.rel = "stylesheet";
  font.href =
    "https://fonts.googleapis.com/css2?family=Exo+2:wght@400;600;700&family=Press+Start+2P&display=swap";
  document.head.appendChild(font);

  var fa = document.createElement("link");
  fa.rel = "stylesheet";
  fa.href =
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css";
  document.head.appendChild(fa);

  var key = "ms-wiki-theme";
  var root = document.documentElement;

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem(key, theme);
    } catch (e) {}
  }

  var saved = null;
  try {
    saved = localStorage.getItem(key);
  } catch (e) {}
  // Default: light; user can switch to dark
  apply(saved === "dark" || saved === "light" ? saved : "light");

  function bind() {
    var btn = document.getElementById("themeToggle");
    if (!btn || btn.dataset.bound) return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(next);
    });
  }
  function visitorKey() {
    var key = "ms-wiki-vid";
    var visitor = null;
    try {
      visitor = localStorage.getItem(key);
    } catch (e) {}
    if (!visitor) {
      visitor =
        (crypto.randomUUID && crypto.randomUUID()) ||
        String(Date.now()) + Math.random().toString(16).slice(2);
      try {
        localStorage.setItem(key, visitor);
      } catch (e) {}
    }
    return String(visitor);
  }

  function trackVisit() {
    try {
      var path = location.pathname + location.search;
      if (path.indexOf("load.php") !== -1 || path.indexOf("/api.php") !== -1) {
        return;
      }
      var payload = JSON.stringify({
        path: path.slice(0, 512),
        visitor_key: visitorKey().slice(0, 64),
      });
      var url = "https://ministation.ru/api/wiki/visit";
      if (navigator.sendBeacon) {
        navigator.sendBeacon(url, new Blob([payload], { type: "text/plain" }));
        return;
      }
      fetch(url, {
        method: "POST",
        headers: { "Content-Type": "text/plain" },
        body: payload,
        keepalive: true,
        mode: "cors",
      }).catch(function () {});
    } catch (e) {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      bind();
      trackVisit();
    });
  } else {
    bind();
    trackVisit();
  }
})();
