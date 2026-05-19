(function () {
  'use strict';
  function renderChart(el) {
    var raw = el.dataset.history;
    if (!raw) return;
    var history;
    try { history = JSON.parse(raw.replace(/&quot;/g, '"')); } catch (e) { return; }
    if (!Array.isArray(history) || history.length < 2) {
      el.textContent = 'Price history not available yet.';
      return;
    }
    var prices = history.map(function (h) { return parseFloat(h.price); }).filter(function (p) { return !isNaN(p); });
    if (prices.length < 2) { el.textContent = 'Price history not available yet.'; return; }
    var W = 600, H = 120, PAD = 24;
    var min = Math.min.apply(null, prices);
    var max = Math.max.apply(null, prices);
    var range = max - min || 1;
    var scaleX = function (i) { return PAD + (i / (prices.length - 1)) * (W - PAD * 2); };
    var scaleY = function (v) { return PAD + (1 - (v - min) / range) * (H - PAD * 2); };
    var polyPts = prices.map(function (p, i) { return scaleX(i) + ',' + scaleY(p); }).join(' ');
    var areaD = 'M' + scaleX(0) + ',' + (H - PAD);
    prices.forEach(function (p, i) { areaD += ' L' + scaleX(i) + ',' + scaleY(p); });
    areaD += ' L' + scaleX(prices.length - 1) + ',' + (H - PAD) + ' Z';
    el.innerHTML = '<svg viewBox="0 0 ' + W + ' ' + H + '" width="100%" role="img" aria-label="Price history chart">'
      + '<defs><linearGradient id="pcg" x1="0" y1="0" x2="0" y2="1">'
      + '<stop offset="0%" stop-color="#e44d26" stop-opacity="0.25"/>'
      + '<stop offset="100%" stop-color="#e44d26" stop-opacity="0"/>'
      + '</linearGradient></defs>'
      + '<path d="' + areaD + '" fill="url(#pcg)"/>'
      + '<polyline points="' + polyPts + '" fill="none" stroke="#e44d26" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
      + '<text x="' + PAD + '" y="' + (H - 6) + '" font-size="11" fill="#666">$' + min.toFixed(2) + '</text>'
      + '<text x="' + (W - PAD) + '" y="' + (H - 6) + '" font-size="11" fill="#666" text-anchor="end">$' + max.toFixed(2) + '</text>'
      + '</svg>';
  }
  document.querySelectorAll('[data-history]').forEach(renderChart);
}());
