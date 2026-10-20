/* Ambient ocean wave + ripple canvas (local port, decorative only). */
(function () {
    'use strict';
    var canvas = document.getElementById('waveCanvas');
    if (!canvas || !canvas.getContext) return;
    var ctx = canvas.getContext('2d');
    if (!ctx) return;

    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var width = 0, height = 0, dpr = 1;
    var ripples = [];
    var mouse = { x: -1000, y: -1000, prevX: -1000, prevY: -1000 };
    var lastSpawn = 0;
    var ambient = 0;
    var time = 0;

    var palette = [
        [2, 132, 199], [14, 165, 233], [0, 103, 129], [56, 189, 248],
        [3, 105, 161], [0, 157, 141], [14, 116, 144], [125, 211, 252]
    ];

    function resize() {
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        width = window.innerWidth;
        height = window.innerHeight;
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);
    }
    window.addEventListener('resize', resize, { passive: true });
    resize();

    function spawn(clientX, clientY, dist) {
        var now = performance.now();
        if (reduce || dist <= 3 || now - lastSpawn < 20) return;
        lastSpawn = now;
        ripples.push({
            x: clientX, y: clientY, radius: 3,
            maxRadius: Math.min(240, 80 + dist * 3),
            strength: Math.min(0.42, 0.16 + dist / 110),
            speed: 2 + Math.min(dist * 0.07, 3.4),
            type: ripples.length % palette.length,
            rings: 4
        });
        if (ripples.length > 42) ripples.shift();
    }

    window.addEventListener('mousemove', function (e) {
        spawn(e.clientX, e.clientY, Math.hypot(e.clientX - mouse.prevX, e.clientY - mouse.prevY));
        mouse.x = mouse.prevX = e.clientX;
        mouse.y = mouse.prevY = e.clientY;
    }, { passive: true });

    function addAmbient() {
        if (reduce) return;
        ripples.push({
            x: Math.random() * width, y: Math.random() * height, radius: 2,
            maxRadius: 120 + Math.random() * 100,
            strength: 0.22, speed: 1.6,
            type: Math.floor(Math.random() * palette.length), rings: 3
        });
        if (ripples.length > 42) ripples.shift();
    }

    function draw() {
        requestAnimationFrame(draw);
        time += reduce ? 0.004 : 0.014;
        if (++ambient % 110 === 0 && ripples.length < 24) addAmbient();
        ctx.clearRect(0, 0, width, height);

        var layers = 6;
        for (var i = 1; i <= layers; i++) {
            var baseY = height * (i / (layers + 1));
            var col = palette[(i - 1) % palette.length];
            ctx.beginPath();
            var segs = 48;
            for (var j = 0; j <= segs; j++) {
                var x = (width / segs) * j;
                var y = baseY +
                    Math.sin(x * 0.0048 + time * (i % 2 ? -1 : 1) + i) * (16 + (i % 3) * 5) +
                    Math.sin(x * 0.011 - time * 0.8 + i * 2) * 8;
                if (j === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
            ctx.strokeStyle = 'rgba(' + col[0] + ',' + col[1] + ',' + col[2] + ',' + (0.16 + i * 0.02).toFixed(3) + ')';
            ctx.lineWidth = 1.6 + i * 0.2;
            ctx.stroke();
        }

        for (var k = ripples.length - 1; k >= 0; k--) {
            var r = ripples[k];
            r.radius += r.speed;
            var p = r.radius / r.maxRadius;
            if (p >= 1) { ripples.splice(k, 1); continue; }
            var alpha = r.strength * (1 - p) * (p < 0.15 ? p / 0.15 : 1);
            var c = palette[r.type];
            for (var ring = 0; ring < r.rings; ring++) {
                var rr = r.radius - ring * 20;
                if (rr <= 2) continue;
                ctx.beginPath();
                ctx.arc(r.x, r.y, rr, 0, Math.PI * 2);
                ctx.strokeStyle = 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + (alpha * (1 - ring / r.rings) * 0.8).toFixed(3) + ')';
                ctx.lineWidth = Math.max(1, 2.4 - ring * 0.4) * (1 - p * 0.6);
                ctx.stroke();
            }
        }
    }

    draw();
})();
