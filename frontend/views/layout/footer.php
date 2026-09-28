</main>
<?php if ($session !== null && $session->isLoggedIn()): ?>
    </div><!-- /.main -->
</div><!-- /.layout -->
<?php endif; ?>
<footer class="footer">KKP EXIM Platform — Market Intelligence &amp; EXIM Automation | &copy; <?= date('Y'); ?></footer>
<script>
(function () {
    var layout = document.getElementById('layout');
    var toggle = document.getElementById('sideToggle');
    if (toggle && layout) {
        toggle.addEventListener('click', function () { layout.classList.toggle('show-side'); });
    }
    var list = document.getElementById('sideList');
    var count = document.getElementById('sideCount');
    var search = document.getElementById('sideSearch');
    if (!list || !search) return;
    var links = Array.prototype.slice.call(list.querySelectorAll('a'));
    function render(filter) {
        var f = (filter || '').toLowerCase();
        var shown = 0;
        links.forEach(function (a) {
            var hit = !f || (a.textContent || '').toLowerCase().indexOf(f) !== -1;
            a.style.display = hit ? '' : 'none';
            if (hit) shown++;
        });
        if (count) count.textContent = shown;
    }
    search.addEventListener('input', function () { render(search.value); });
    render('');
})();
</script>
</body>
</html>