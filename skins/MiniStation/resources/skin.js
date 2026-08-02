(function () {
  var font = document.createElement("link");
  font.rel = "stylesheet";
  font.href =
    "https://fonts.googleapis.com/css2?family=Exo+2:wght@400;600;700&family=Press+Start+2P&display=swap";
  document.head.appendChild(font);

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
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})();
