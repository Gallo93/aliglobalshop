(function () {
  var banner = document.getElementById('cookie-banner');
  if (!banner) return;
  try {
    if (localStorage.getItem('cookie_consent')) {
      banner.hidden = true;
      return;
    }
    var acceptBtn = document.getElementById('cookie-accept');
    var declineBtn = document.getElementById('cookie-decline');
    if (acceptBtn) {
      acceptBtn.addEventListener('click', function () {
        try { localStorage.setItem('cookie_consent', 'yes'); } catch (e) {}
        banner.hidden = true;
      });
    }
    if (declineBtn) {
      declineBtn.addEventListener('click', function () {
        try { localStorage.setItem('cookie_consent', 'no'); } catch (e) {}
        banner.hidden = true;
      });
    }
  } catch (e) {
    // localStorage non disponibile (Safari private mode) - banner resta visibile
  }
}());
