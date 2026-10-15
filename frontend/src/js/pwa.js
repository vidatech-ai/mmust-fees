(function () {
  var here = document.currentScript.src;
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register(new URL("../../sw.js", here)).catch(function () {});
  }
  var btn = document.getElementById("installBtn");
  if (!btn) return;
  var note = document.getElementById("installNote");
  var deferred = null;
  var ua = navigator.userAgent;
  var standalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  var isIpad = /ipad/i.test(ua) || (/macintosh/i.test(ua) && navigator.maxTouchPoints > 1);
  var isIos = /iphone|ipod/i.test(ua) || isIpad;
  var isMobile = isIos || /android|mobile/i.test(ua);
  var isFirefox = /firefox|fxios/i.test(ua);
  var isSafari = /safari/i.test(ua) && !/chrome|crios|chromium|edg|fxios|opr/i.test(ua);

  function only(text) { btn.style.display = "none"; note.textContent = text; }

  if (standalone) return only("The app is already installed on this device.");
  if (isIos) {
    return only(isSafari
      ? "Tap the Share button, then choose Add to Home Screen."
      : "Open this link in Safari, tap the Share button, then choose Add to Home Screen.");
  }
  if (!isMobile && isSafari) return only("In Safari, open the File menu and choose Add to Dock.");
  if (!isMobile && isFirefox) return only("Firefox cannot install apps on laptops. Open this link in Chrome or Edge instead.");

  window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); deferred = e; });
  window.addEventListener("appinstalled", function () { btn.style.display = "none"; note.textContent = "Installed. Open C-Med MMUST from your home screen, desktop or start menu."; });
  btn.addEventListener("click", function () {
    if (deferred) { deferred.prompt(); deferred = null; }
    else note.textContent = isMobile
      ? "Open your browser menu (the three dots) and tap Install app or Add to Home screen."
      : "Click the install icon at the right end of the address bar, or open the browser menu and choose Install C-Med MMUST.";
  });
})();
