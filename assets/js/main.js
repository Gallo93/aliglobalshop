document.querySelectorAll('img[data-src]').forEach(img => {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        img.src = img.dataset.src;
        observer.unobserve(img);
      }
    });
  });
  observer.observe(img);
});

(function () {
  var hamburger = document.querySelector('.nav__hamburger');
  var nav = document.querySelector('.nav');
  if (!hamburger || !nav) return;
  hamburger.addEventListener('click', function (e) {
    e.stopPropagation();
    var open = nav.classList.toggle('nav--open');
    hamburger.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('click', function (e) {
    if (nav.classList.contains('nav--open') && !nav.contains(e.target)) {
      nav.classList.remove('nav--open');
      hamburger.setAttribute('aria-expanded', 'false');
    }
  });
}());
