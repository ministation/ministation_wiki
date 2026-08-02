(function () {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;
  const icon = btn.querySelector("i");
  function syncIcon() {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    if (icon) icon.className = dark ? "fa-solid fa-sun" : "fa-solid fa-moon";
  }
  syncIcon();
  btn.addEventListener("click", () => {
    const next =
      document.documentElement.getAttribute("data-theme") === "dark"
        ? "light"
        : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("ms-wiki-theme", next);
    syncIcon();
  });
})();
