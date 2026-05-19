// AliGlobalShop — particle engine
// Single shared canvas + per-effect emitter behaviors

const DPR = Math.max(1, Math.min(2, window.devicePixelRatio || 1));

class Particle {
  constructor(opts) { Object.assign(this, opts); this.born = performance.now(); }
  isDead(now) { return now - this.born > this.life; }
  age(now) { return (now - this.born) / this.life; }
}

const EFFECTS = {
  electric(sys, x, y, n = 1) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const v = 60 + Math.random() * 180;
      sys.particles.push(new Particle({
        kind: 'electric', x, y,
        vx: Math.cos(a) * v, vy: Math.sin(a) * v,
        life: 320 + Math.random() * 280,
        seg: 3 + Math.floor(Math.random() * 3),
        hue: 200 + Math.random() * 30,
        size: 1 + Math.random() * 1.5,
      }));
    }
  },
  glow(sys, x, y, n = 1) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const v = 20 + Math.random() * 60;
      sys.particles.push(new Particle({
        kind: 'glow', x, y,
        vx: Math.cos(a) * v, vy: Math.sin(a) * v - 30,
        life: 800 + Math.random() * 400,
        hue: 140 + Math.random() * 40,
        size: 4 + Math.random() * 8,
      }));
    }
  },
  streak(sys, x, y, n = 1) {
    for (let i = 0; i < n; i++) {
      const a = -Math.PI / 2 + (Math.random() - 0.5) * 1.2;
      const v = 120 + Math.random() * 200;
      sys.particles.push(new Particle({
        kind: 'streak', x, y,
        vx: Math.cos(a) * v, vy: Math.sin(a) * v,
        life: 400 + Math.random() * 200,
        hue: 20 + Math.random() * 30,
        size: 2 + Math.random() * 2,
        len: 20 + Math.random() * 40,
      }));
    }
  },
  glitch(sys, x, y, n = 1) {
    for (let i = 0; i < n; i++) {
      sys.particles.push(new Particle({
        kind: 'glitch', x, y,
        vx: (Math.random() - 0.5) * 160,
        vy: (Math.random() - 0.5) * 160,
        life: 200 + Math.random() * 300,
        hue: Math.random() * 360,
        size: 2 + Math.floor(Math.random() * 6),
        w: 4 + Math.floor(Math.random() * 12),
        h: 2 + Math.floor(Math.random() * 4),
      }));
    }
  },
  fire(sys, x, y, n = 1) {
    for (let i = 0; i < n; i++) {
      const v = 60 + Math.random() * 100;
      sys.particles.push(new Particle({
        kind: 'fire', x, y,
        vx: (Math.random() - 0.5) * 60,
        vy: -(v),
        life: 500 + Math.random() * 300,
        hue: 10 + Math.random() * 40,
        size: 4 + Math.random() * 8,
      }));
    }
  },
  confetti(sys, x, y, n = 1) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      sys.particles.push(new Particle({
        kind: 'confetti', x, y,
        vx: Math.cos(a) * (40 + Math.random() * 80),
        vy: -(60 + Math.random() * 120),
        life: 900 + Math.random() * 400,
        hue: Math.random() * 360,
        size: 5 + Math.random() * 5,
        rot: Math.random() * Math.PI * 2,
        rotV: (Math.random() - 0.5) * 8,
        gravity: 120,
      }));
    }
  },
  ink(sys, x, y, n = 1) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const v = 30 + Math.random() * 80;
      sys.particles.push(new Particle({
        kind: 'ink', x, y,
        vx: Math.cos(a) * v, vy: Math.sin(a) * v,
        life: 600 + Math.random() * 400,
        hue: 260 + Math.random() * 60,
        size: 6 + Math.random() * 10,
      }));
    }
  },
};

class ParticleSystem {
  constructor(container) {
    this.particles = [];
    this.canvas = document.createElement('canvas');
    this.canvas.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:10;';
    container.style.position = 'relative';
    container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');
    this.resize();
    new ResizeObserver(() => this.resize()).observe(container);
    this._raf = null;
    this.tick = this.tick.bind(this);
  }
  resize() {
    const r = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = r.width * DPR;
    this.canvas.height = r.height * DPR;
    this.canvas.style.width = r.width + 'px';
    this.canvas.style.height = r.height + 'px';
    this.ctx.scale(DPR, DPR);
  }
  emit(type, x, y, n) {
    EFFECTS[type]?.(this, x, y, n);
    if (!this._raf) this._raf = requestAnimationFrame(this.tick);
  }
  tick(now) {
    this.particles = this.particles.filter(p => !p.isDead(now));
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    for (const p of this.particles) {
      const t = p.age(now);
      const dt = 1 / 60;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      if (p.gravity) p.vy += p.gravity * dt;
      p.vx *= 0.98; p.vy *= 0.98;
      const a = 1 - t;
      if (p.kind === 'electric') {
        ctx.save(); ctx.strokeStyle = `hsla(${p.hue},100%,70%,${a})`; ctx.lineWidth = p.size;
        ctx.beginPath(); ctx.moveTo(p.x, p.y);
        for (let s = 0; s < p.seg; s++) ctx.lineTo(p.x + (Math.random() - 0.5) * 20, p.y + (Math.random() - 0.5) * 20);
        ctx.stroke(); ctx.restore();
      } else if (p.kind === 'glow') {
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * (1 - t * 0.5));
        g.addColorStop(0, `hsla(${p.hue},100%,70%,${a * 0.8})`);
        g.addColorStop(1, `hsla(${p.hue},100%,50%,0)`);
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.x, p.y, p.size * (1 - t * 0.5), 0, Math.PI * 2); ctx.fill();
      } else if (p.kind === 'streak') {
        ctx.save(); ctx.strokeStyle = `hsla(${p.hue},100%,60%,${a})`; ctx.lineWidth = p.size;
        ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(p.x - p.vx * 0.05, p.y - p.vy * 0.05); ctx.stroke(); ctx.restore();
      } else if (p.kind === 'glitch') {
        ctx.fillStyle = `hsla(${p.hue},100%,60%,${a})`; ctx.fillRect(p.x, p.y, p.w, p.h);
      } else if (p.kind === 'fire') {
        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size);
        g.addColorStop(0, `hsla(${p.hue + 20},100%,80%,${a})`);
        g.addColorStop(0.5, `hsla(${p.hue},100%,50%,${a * 0.7})`);
        g.addColorStop(1, `hsla(${p.hue - 10},100%,30%,0)`);
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(p.x, p.y, p.size * (1 - t * 0.4), 0, Math.PI * 2); ctx.fill();
      } else if (p.kind === 'confetti') {
        p.rot += p.rotV * dt;
        ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
        ctx.fillStyle = `hsla(${p.hue},90%,60%,${a})`; ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2); ctx.restore();
      } else if (p.kind === 'ink') {
        ctx.fillStyle = `hsla(${p.hue},60%,40%,${a * 0.7})`; ctx.beginPath(); ctx.arc(p.x, p.y, p.size * (1 - t * 0.3), 0, Math.PI * 2); ctx.fill();
      }
    }
    this._raf = this.particles.length ? requestAnimationFrame(this.tick) : null;
  }
}

function initParticles() {
  document.querySelectorAll('[data-particles]').forEach(el => {
    const type = el.dataset.particles;
    const sys = new ParticleSystem(el);
    el.addEventListener('mouseenter', e => {
      const r = el.getBoundingClientRect();
      sys.emit(type, r.width / 2, r.height / 2, 12);
    });
    el.addEventListener('mousemove', e => {
      const r = el.getBoundingClientRect();
      if (Math.random() < 0.3) sys.emit(type, e.clientX - r.left, e.clientY - r.top, 2);
    });
    el.addEventListener('click', e => {
      const r = el.getBoundingClientRect();
      sys.emit(type, e.clientX - r.left, e.clientY - r.top, 20);
    });
  });
}

function initHeroCanvas() {
  const hero = document.querySelector('.hero');
  if (!hero) return;
  const canvas = document.createElement('canvas');
  canvas.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:0;opacity:0.6;';
  hero.style.position = 'relative';
  hero.insertBefore(canvas, hero.firstChild);
  const ctx = canvas.getContext('2d');
  const resize = () => { canvas.width = hero.offsetWidth * DPR; canvas.height = hero.offsetHeight * DPR; };
  resize();
  window.addEventListener('resize', resize);
  const dots = Array.from({ length: 80 }, () => ({
    x: Math.random() * canvas.width / DPR,
    y: Math.random() * canvas.height / DPR,
    vx: (Math.random() - 0.5) * 0.4, vy: (Math.random() - 0.5) * 0.4,
    size: 0.5 + Math.random() * 2,
    hue: Math.random() < 0.5 ? 20 : 200 + Math.random() * 40,
    a: 0.2 + Math.random() * 0.5,
  }));
  (function loop() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save(); ctx.scale(DPR, DPR);
    for (const d of dots) {
      d.x += d.vx; d.y += d.vy;
      if (d.x < 0) d.x = canvas.width / DPR;
      if (d.x > canvas.width / DPR) d.x = 0;
      if (d.y < 0) d.y = canvas.height / DPR;
      if (d.y > canvas.height / DPR) d.y = 0;
      ctx.beginPath(); ctx.arc(d.x, d.y, d.size, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${d.hue},80%,60%,${d.a})`; ctx.fill();
    }
    for (let i = 0; i < dots.length; i++) for (let j = i + 1; j < dots.length; j++) {
      const dx = dots[i].x - dots[j].x, dy = dots[i].y - dots[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 80) { ctx.strokeStyle = `rgba(228,77,38,${0.15 * (1 - dist / 80)})`; ctx.lineWidth = 0.5; ctx.beginPath(); ctx.moveTo(dots[i].x, dots[i].y); ctx.lineTo(dots[j].x, dots[j].y); ctx.stroke(); }
    }
    ctx.restore();
    requestAnimationFrame(loop);
  })();
}

document.addEventListener('DOMContentLoaded', () => { initParticles(); initHeroCanvas(); });
