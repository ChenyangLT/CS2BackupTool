// 滚动显现
const io = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
      io.unobserve(entry.target);
    }
  });
}, { threshold: 0.12 });
document.querySelectorAll('.reveal').forEach((el) => io.observe(el));

// 3D 倾斜效果（鼠标跟踪）
document.querySelectorAll('[data-tilt]').forEach((card) => {
  card.addEventListener('mousemove', (e) => {
    const r = card.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    card.style.transform =
      `perspective(900px) rotateY(${x * 14}deg) rotateX(${-y * 14}deg) translateY(-8px)`;
  });
  card.addEventListener('mouseleave', () => {
    card.style.transform = '';
  });
});

// 平滑滚动（已由 CSS scroll-behavior 处理，这里额外处理锚点偏移）
document.querySelectorAll('a[href^="#"]').forEach((a) => {
  a.addEventListener('click', (e) => {
    const id = a.getAttribute('href');
    const el = document.querySelector(id);
    if (el) {
      e.preventDefault();
      el.scrollIntoView({ behavior: 'smooth' });
    }
  });
});
