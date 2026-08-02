(function () {
  const key = "ms-wiki-theme";
  const saved = localStorage.getItem(key);
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.setAttribute(
    "data-theme",
    saved || (prefersDark ? "dark" : "light")
  );
})();
