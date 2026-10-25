/* neural-bg.js – Subtle ethereal ambient light for Kavach Legal Theme */
(function () {
  'use strict';

  var COLOR = [0.92, 0.95, 0.99];
  var OPACITY = 0.4;
  var SPEED = 0.0008;

  var VERT_SRC =
    'precision mediump float;\n' +
    'varying vec2 vUv;\n' +
    'attribute vec2 a_position;\n' +
    'void main() {\n' +
    '  vUv = 0.5 * (a_position + 1.0);\n' +
    '  gl_Position = vec4(a_position, 0.0, 1.0);\n' +
    '}';

  var FRAG_SRC =
    'precision mediump float;\n' +
    'varying vec2 vUv;\n' +
    'uniform float u_time;\n' +
    'uniform float u_ratio;\n' +
    'uniform vec2 u_pointer_position;\n' +
    'uniform vec3 u_color;\n' +
    'uniform float u_speed;\n' +
    'vec2 rotate(vec2 uv, float th) {\n' +
    '  return mat2(cos(th), sin(th), -sin(th), cos(th)) * uv;\n' +
    '}\n' +
    'float neuro_shape(vec2 uv, float t, float p) {\n' +
    '  vec2 sine_acc = vec2(0.0);\n' +
    '  vec2 res = vec2(0.0);\n' +
    '  float scale = 8.0;\n' +
    '  for (int j = 0; j < 15; j++) {\n' +
    '    uv = rotate(uv, 1.0);\n' +
    '    sine_acc = rotate(sine_acc, 1.0);\n' +
    '    vec2 layer = uv * scale + float(j) + sine_acc - t;\n' +
    '    sine_acc += sin(layer) + 2.4 * p;\n' +
    '    res += (0.5 + 0.5 * cos(layer)) / scale;\n' +
    '    scale *= 1.2;\n' +
    '  }\n' +
    '  return res.x + res.y;\n' +
    '}\n' +
    'void main() {\n' +
    '  vec2 uv = 0.5 * vUv;\n' +
    '  uv.x *= u_ratio;\n' +
    '  vec2 pointer = vUv - u_pointer_position;\n' +
    '  pointer.x *= u_ratio;\n' +
    '  float p = clamp(length(pointer), 0.0, 1.0);\n' +
    '  p = 0.5 * pow(1.0 - p, 2.0);\n' +
    '  float t = u_speed * u_time;\n' +
    '  vec3 col = vec3(0.0);\n' +
    '  float noise = neuro_shape(uv, t, p);\n' +
    '  noise = 1.2 * pow(noise, 3.0); noise += pow(noise, 10.0);\n' +
    '  noise = max(0.0, noise - 0.5);\n' +
    '  noise *= (1.0 - length(vUv - 0.5));\n' +
    '  col = u_color * noise;\n' +
    '  gl_FragColor = vec4(col, noise * 0.4);\n' +
    '}';

  var canvas, gl, program;
  var uTime, uRatio, uPointer, uColor, uSpeed;
  var pointer = { x: 0, y: 0, tX: 0, tY: 0 };
  var rafId = null;
  var lastFrame = 0;
  var FPS_INTERVAL = 1000 / 30;
  var reducedMotion = false;
  var resizeTimer = null;

  function init() {
    canvas = document.getElementById('bg-canvas');
    if (!canvas) return;

    reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    try {
      gl = canvas.getContext('webgl', { alpha: true, antialias: false, depth: false, stencil: false }) ||
           canvas.getContext('experimental-webgl', { alpha: true, antialias: false, depth: false, stencil: false });
    } catch (e) {
      gl = null;
    }
    if (!gl) {
      fallback();
      return;
    }

    var vs = compileShader(gl.VERTEX_SHADER, VERT_SRC);
    var fs = compileShader(gl.FRAGMENT_SHADER, FRAG_SRC);
    if (!vs || !fs) {
      fallback();
      return;
    }

    program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      fallback();
      return;
    }

    gl.useProgram(program);

    var buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

    var aPos = gl.getAttribLocation(program, 'a_position');
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

    uTime = gl.getUniformLocation(program, 'u_time');
    uRatio = gl.getUniformLocation(program, 'u_ratio');
    uPointer = gl.getUniformLocation(program, 'u_pointer_position');
    uColor = gl.getUniformLocation(program, 'u_color');
    uSpeed = gl.getUniformLocation(program, 'u_speed');

    gl.uniform3f(uColor, COLOR[0], COLOR[1], COLOR[2]);
    gl.uniform1f(uSpeed, SPEED);

    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

    canvas.style.opacity = OPACITY;

    pointer.x = window.innerWidth * 0.5;
    pointer.y = window.innerHeight * 0.5;
    pointer.tX = pointer.x;
    pointer.tY = pointer.y;

    resizeCanvas();

    window.addEventListener('resize', onResize);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('touchmove', onTouchMove, { passive: true });
    window.addEventListener('click', onClick);
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('beforeunload', cleanup);

    if (reducedMotion) {
      render(performance.now());
    } else {
      lastFrame = performance.now();
      rafId = requestAnimationFrame(loop);
    }
  }

  function compileShader(type, src) {
    var s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      gl.deleteShader(s);
      return null;
    }
    return s;
  }

  function fallback() {
    document.documentElement.classList.add('no-webgl');
    cleanup();
  }

  function resizeCanvas() {
    var dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    var w = window.innerWidth || 1;
    var h = window.innerHeight || 1;
    canvas.width = Math.max(1, Math.floor(w * dpr));
    canvas.height = Math.max(1, Math.floor(h * dpr));
    if (gl) {
      gl.viewport(0, 0, canvas.width, canvas.height);
      if (uRatio) {
        gl.uniform1f(uRatio, canvas.width / canvas.height);
      }
    }
  }

  function onResize() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(resizeCanvas, 100);
  }

  function updateMousePosition(x, y) {
    pointer.tX = x;
    pointer.tY = y;
  }

  function onPointerMove(e) {
    updateMousePosition(e.clientX, e.clientY);
  }

  function onTouchMove(e) {
    if (e.targetTouches && e.targetTouches[0]) {
      updateMousePosition(e.targetTouches[0].clientX, e.targetTouches[0].clientY);
    }
  }

  function onClick(e) {
    updateMousePosition(e.clientX, e.clientY);
  }

  function onVisibility() {
    if (document.hidden) {
      if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
    } else if (!reducedMotion && !rafId) {
      lastFrame = performance.now();
      rafId = requestAnimationFrame(loop);
    }
  }

  function loop(now) {
    rafId = requestAnimationFrame(loop);
    var delta = now - lastFrame;
    if (delta < FPS_INTERVAL) return;
    lastFrame = now - (delta % FPS_INTERVAL);
    render(now);
  }

  function render(now) {
    pointer.x += (pointer.tX - pointer.x) * 0.2;
    pointer.y += (pointer.tY - pointer.y) * 0.2;
    gl.uniform1f(uTime, now);
    if (uRatio) {
      gl.uniform1f(uRatio, canvas.width / (canvas.height || 1));
    }
    var winW = window.innerWidth || 1;
    var winH = window.innerHeight || 1;
    gl.uniform2f(uPointer, pointer.x / winW, 1.0 - (pointer.y / winH));
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  function cleanup() {
    if (rafId) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
    window.removeEventListener('resize', onResize);
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('touchmove', onTouchMove);
    window.removeEventListener('click', onClick);
    document.removeEventListener('visibilitychange', onVisibility);
    clearTimeout(resizeTimer);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
