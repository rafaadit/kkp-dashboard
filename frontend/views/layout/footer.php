</main>
<?php $footer_logo = @filemtime(__DIR__ . '/../../public/assets/logo-kkp.png') ?: time(); ?>
<footer class="footer">
  <div class="footer-inner">
    <div class="footer-brand">
      <img class="footer-logo" src="/assets/logo-kkp.png?v=<?= $footer_logo; ?>" alt="Logo Kementerian Kelautan dan Perikanan" width="30" height="30">
      <span><?= KKP\View::e($appName ?? 'KKP EXIM Platform'); ?></span>
    </div>
    <div class="footer-src">
      <span>Sumber Data Terverifikasi:</span>
      <strong>KKP RI</strong><span>&middot;</span>
      <strong>Badan Pusat Statistik</strong><span>&middot;</span>
      <strong>ITC Trade Map</strong>
    </div>
    <div class="footer-copy">&copy; <?= date('Y'); ?> KKP EXIM Platform. Hak Cipta Dilindungi.</div>
  </div>
</footer>
<script src="/assets/waves.js?v=<?= @filemtime(__DIR__ . '/../../public/assets/waves.js') ?: time(); ?>"></script>
<script>
(function () {
    var nav = document.getElementById('topnav');
    var navToggle = document.getElementById('navToggle');
    if (nav && navToggle) {
        navToggle.addEventListener('click', function () {
            var open = nav.classList.toggle('nav-open');
            navToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
    }
    Array.prototype.forEach.call(document.querySelectorAll('.nav-drop > .nav-link'), function (btn) {
        btn.addEventListener('click', function (e) {
            var drop = btn.parentNode;
            if (window.matchMedia('(max-width: 900px)').matches) {
                e.preventDefault();
                drop.classList.toggle('open');
            }
        });
    });

    var input = document.getElementById('komSearch');
    var menu = document.getElementById('komMenu');
    if (input && menu) {
        var links = Array.prototype.slice.call(menu.querySelectorAll('a'));
        var empty = menu.querySelector('.empty');
        function filter() {
            var q = (input.value || '').toLowerCase().trim();
            var shown = 0;
            links.forEach(function (a) {
                var hit = !q || (a.textContent || '').toLowerCase().indexOf(q) !== -1;
                a.style.display = hit ? '' : 'none';
                if (hit) shown++;
            });
            if (!links.length && empty) empty.style.display = q ? 'none' : '';
        }
        function open() { menu.classList.add('open'); filter(); }
        input.addEventListener('focus', open);
        input.addEventListener('input', open);
        document.addEventListener('click', function (e) {
            if (!menu.contains(e.target) && e.target !== input) menu.classList.remove('open');
        });
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') { menu.classList.remove('open'); input.blur(); }
        });
    }
    var hero = document.querySelector('.hero-slider');
    if (hero) {
        var slides = Array.prototype.slice.call(hero.querySelectorAll('.hero-slide'));
        var dots = Array.prototype.slice.call(hero.querySelectorAll('.hero-slide-dot'));
        var interval = Number(hero.dataset.slideInterval || 3000);
        var activeSlide = 0;
        var timer = null;
        var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        function showSlide(index) {
            activeSlide = (index + slides.length) % slides.length;
            slides.forEach(function (slide, i) { slide.classList.toggle('is-active', i === activeSlide); });
            dots.forEach(function (dot, i) {
                dot.classList.toggle('is-active', i === activeSlide);
                if (i === activeSlide) dot.setAttribute('aria-current', 'true');
                else dot.removeAttribute('aria-current');
            });
        }

        function startSlider() {
            if (timer || reduceMotion || slides.length < 2) return;
            timer = window.setInterval(function () { showSlide(activeSlide + 1); }, interval);
        }

        function stopSlider() { if (timer) window.clearInterval(timer); timer = null; }

        dots.forEach(function (dot, i) {
            dot.addEventListener('click', function () { showSlide(i); stopSlider(); startSlider(); });
        });
        hero.addEventListener('mouseenter', stopSlider);
        hero.addEventListener('mouseleave', startSlider);
        hero.addEventListener('focusin', stopSlider);
        hero.addEventListener('focusout', startSlider);
        startSlider();
    }
})();
</script>
</body>
</html>
