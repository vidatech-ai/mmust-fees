(function () {
  var here = document.currentScript.src;
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(new URL("../../sw.js", here)).catch(function () {});
  }
  var btn = document.getElementById("installBtn");
  if (!btn) return;
  var note = document.getElementById("installNote");
  var deferred = null;
  var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  var ios = /iphone|ipad|ipod/i.test(navigator.userAgent);

  if (standalone) { btn.style.display = "none"; note.textContent = "The app is already installed on this device."; return; }
  if (ios) { btn.style.display = "none"; note.textContent = "On iPhone: open this page in Safari, tap the Share button, then choose Add to Home Screen."; return; }

  window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); deferred = e; });
  window.addEventListener("appinstalled", function () { btn.style.display = "none"; note.textContent = "Installed. Open C-Med MMUST from your home screen."; });
  btn.addEventListener("click", function () {
    if (deferred) { deferred.prompt(); deferred = null; }
    else note.textContent = "Open your browser menu (the three dots) and tap Install app or Add to Home screen.";
  });
})();
