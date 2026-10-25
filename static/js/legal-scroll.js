/* legal-scroll.js – Real 3D Scales of Justice on Every Page & Scroll Navigator */
(function () {
  'use strict';

  function init() {
    var container = document.querySelector('.page-container');
    if (!container) return;

    // 0. Clean emojis from Data Map mode switcher buttons (replace with SVG vectors)
    var btnSources = document.getElementById('mode-btn-sources');
    if (btnSources && !btnSources.querySelector('.mode-icon')) {
      btnSources.innerHTML = '<span class="mode-icon mode-icon-sources" aria-hidden="true"></span> Sources &rarr; Categories';
    }
    var btnPerson = document.getElementById('mode-btn-person');
    if (btnPerson && !btnPerson.querySelector('.mode-icon')) {
      btnPerson.innerHTML = '<span class="mode-icon mode-icon-person" aria-hidden="true"></span> Person View (Entity Resolution)';
    }

    // 1. Vertical 4-Dot Section Navigator (Active on Dashboard)
    var isDashboard = document.querySelector('.dashboard-page');
    if (isDashboard) {
      initScrollNav();
    }

    // 2. Mount 3D Stage on Each Page
    var stage = document.createElement('div');
    stage.className = 'taraju-stage';
    stage.setAttribute('aria-hidden', 'true');

    var canvas = document.createElement('canvas');
    canvas.className = 'taraju-3d-canvas';
    stage.appendChild(canvas);
    container.appendChild(stage);

    // 3. Load Three.js if needed and initialize 3D Model
    if (window.THREE) {
      init3D(canvas, stage);
    } else {
      var script = document.createElement('script');
      script.src = '/static/vendor/three.min.js';
      script.onload = function () {
        init3D(canvas, stage);
      };
      document.head.appendChild(script);
    }
  }

  function initScrollNav() {
    var nav = document.createElement('div');
    nav.className = 'legal-scroll-nav';
    nav.setAttribute('aria-label', 'Section Navigator');

    var track = document.createElement('div');
    track.className = 'scroll-track';
    nav.appendChild(track);

    var dots = [];
    var labels = ['Welcome', 'Inventory', 'Compliance', 'Resolution'];

    for (var d = 0; d < 4; d++) {
      var dot = document.createElement('div');
      dot.className = 'scroll-dot' + (d === 0 ? ' active' : '');
      dot.setAttribute('data-index', d);

      var bead = document.createElement('span');
      bead.className = 'dot-bead';

      var label = document.createElement('span');
      label.textContent = labels[d];
      label.className = 'dot-label';

      dot.appendChild(label);
      dot.appendChild(bead);
      nav.appendChild(dot);
      dots.push(dot);

      (function (index) {
        dot.addEventListener('click', function () {
          var maxScroll = document.documentElement.scrollHeight - window.innerHeight;
          var targets = [0, maxScroll * 0.32, maxScroll * 0.65, maxScroll];
          window.scrollTo({
            top: targets[index],
            behavior: 'smooth'
          });
        });
      })(d);
    }
    document.body.appendChild(nav);

    function onScroll() {
      var scrollY = window.pageYOffset || document.documentElement.scrollTop || 0;
      var maxScroll = (document.documentElement.scrollHeight - window.innerHeight) || 1;
      var progress = Math.min(Math.max(scrollY / maxScroll, 0), 1);

      var activeIndex = 0;
      if (progress < 0.22) {
        activeIndex = 0;
      } else if (progress < 0.52) {
        activeIndex = 1;
      } else if (progress < 0.82) {
        activeIndex = 2;
      } else {
        activeIndex = 3;
      }

      for (var k = 0; k < dots.length; k++) {
        if (k === activeIndex) {
          dots[k].classList.add('active');
        } else {
          dots[k].classList.remove('active');
        }
      }
    }

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  function init3D(canvas, stage) {
    var THREE = window.THREE;
    if (!THREE) return;

    var isDashboard = !!document.querySelector('.dashboard-page');
    var isCompact = !isDashboard;

    var defaultWidth = isCompact ? 220 : 380;
    var defaultHeight = isCompact ? 200 : 400;

    var width = stage.clientWidth || defaultWidth;
    var height = stage.clientHeight || defaultHeight;

    // Renderer
    var renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance'
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height);
    if (renderer.toneMapping !== undefined) {
      renderer.toneMapping = THREE.ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.15;
    }

    // Scene & Camera (Compact framing on content pages, hero framing on dashboard)
    var modelScale = isCompact ? 0.58 : 0.63;
    var camZ = isCompact ? 7.8 : 7.5;

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(36, width / height, 0.1, 50);
    camera.position.set(0, 0.5, camZ);
    camera.lookAt(0, 0.5, 0);

    // Root Group for smooth in-place rotation
    var rootGroup = new THREE.Group();
    rootGroup.scale.set(modelScale, modelScale, modelScale);
    scene.add(rootGroup);

    // Materials (Physically Based Gold Shaders)
    var goldPolished = new THREE.MeshStandardMaterial({
      color: 0xdfaf3e,
      roughness: 0.18,
      metalness: 0.92
    });

    var goldAntique = new THREE.MeshStandardMaterial({
      color: 0xc8982c,
      roughness: 0.32,
      metalness: 0.86
    });

    var goldBowl = new THREE.MeshStandardMaterial({
      color: 0xebbf48,
      roughness: 0.2,
      metalness: 0.9,
      side: THREE.DoubleSide
    });

    var goldChain = new THREE.MeshStandardMaterial({
      color: 0xd4a530,
      roughness: 0.25,
      metalness: 0.88
    });

    // Helper: 3D cylinder connecting two points
    function createChain(p1, p2, r, mat) {
      var v = new THREE.Vector3().subVectors(p2, p1);
      var len = v.length();
      var geom = new THREE.CylinderGeometry(r, r, len, 8);
      var mesh = new THREE.Mesh(geom, mat);
      var mid = new THREE.Vector3().addVectors(p1, p2).multiplyScalar(0.5);
      mesh.position.copy(mid);
      mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), v.clone().normalize());
      return mesh;
    }

    // 1. Pedestal Base (Ornate Stepped Gold Base)
    var b1 = new THREE.Mesh(new THREE.CylinderGeometry(1.55, 1.68, 0.24, 48), goldAntique);
    b1.position.y = -1.45;
    rootGroup.add(b1);

    var b2 = new THREE.Mesh(new THREE.CylinderGeometry(1.32, 1.46, 0.18, 48), goldPolished);
    b2.position.y = -1.25;
    rootGroup.add(b2);

    var bTorus = new THREE.Mesh(new THREE.TorusGeometry(1.18, 0.07, 16, 48), goldAntique);
    bTorus.position.y = -1.16;
    bTorus.rotation.x = Math.PI / 2;
    rootGroup.add(bTorus);

    var bDome = new THREE.Mesh(new THREE.CylinderGeometry(0.44, 1.16, 0.48, 48), goldAntique);
    bDome.position.y = -0.92;
    rootGroup.add(bDome);

    var bCollar = new THREE.Mesh(new THREE.TorusGeometry(0.44, 0.05, 16, 32), goldPolished);
    bCollar.position.y = -0.68;
    bCollar.rotation.x = Math.PI / 2;
    rootGroup.add(bCollar);

    // 2. Central Fluted Column (Pillar)
    var colBase = new THREE.Mesh(new THREE.CylinderGeometry(0.25, 0.35, 0.35, 32), goldAntique);
    colBase.position.y = -0.5;
    rootGroup.add(colBase);

    var pillar = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.23, 2.35, 32), goldPolished);
    pillar.position.y = 0.82;
    rootGroup.add(pillar);

    var colRing = new THREE.Mesh(new THREE.TorusGeometry(0.24, 0.045, 16, 32), goldPolished);
    colRing.position.y = 0.62;
    colRing.rotation.x = Math.PI / 2;
    rootGroup.add(colRing);

    var colCapital = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.17, 0.28, 32), goldAntique);
    colCapital.position.y = 1.98;
    rootGroup.add(colCapital);

    // Fulcrum Hub
    var hub = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.26, 24), goldPolished);
    hub.position.y = 2.18;
    hub.rotation.z = Math.PI / 2;
    rootGroup.add(hub);

    // Spire of Justice (Top Finial)
    var finialSphere = new THREE.Mesh(new THREE.SphereGeometry(0.19, 24, 16), goldPolished);
    finialSphere.position.y = 2.45;
    rootGroup.add(finialSphere);

    var spire = new THREE.Mesh(new THREE.ConeGeometry(0.12, 0.48, 24), goldPolished);
    spire.position.y = 2.76;
    rootGroup.add(spire);

    // 3. Balance Assembly (Tilting Beam + Hanging Pans)
    var balanceArm = new THREE.Group();
    balanceArm.position.y = 2.18;
    rootGroup.add(balanceArm);

    // Left Curved Arch Beam
    var pLeft = [
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(-0.65, 0.22, 0),
      new THREE.Vector3(-1.45, 0.16, 0),
      new THREE.Vector3(-2.15, -0.06, 0)
    ];
    var curveL = new THREE.CatmullRomCurve3(pLeft);
    var beamLeft = new THREE.Mesh(new THREE.TubeGeometry(curveL, 32, 0.065, 16, false), goldPolished);
    balanceArm.add(beamLeft);

    // Right Curved Arch Beam
    var pRight = [
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(0.65, 0.22, 0),
      new THREE.Vector3(1.45, 0.16, 0),
      new THREE.Vector3(2.15, -0.06, 0)
    ];
    var curveR = new THREE.CatmullRomCurve3(pRight);
    var beamRight = new THREE.Mesh(new THREE.TubeGeometry(curveR, 32, 0.065, 16, false), goldPolished);
    balanceArm.add(beamRight);

    // Center decorative arch crest
    var crest = new THREE.Mesh(new THREE.TorusGeometry(0.36, 0.035, 16, 32, Math.PI), goldAntique);
    crest.position.y = 0.06;
    balanceArm.add(crest);

    // End Hook Rings
    var hookL = new THREE.Mesh(new THREE.TorusGeometry(0.11, 0.032, 16, 24), goldPolished);
    hookL.position.set(-2.15, -0.16, 0);
    balanceArm.add(hookL);

    var hookR = new THREE.Mesh(new THREE.TorusGeometry(0.11, 0.032, 16, 24), goldPolished);
    hookR.position.set(2.15, -0.16, 0);
    balanceArm.add(hookR);

    // 4. Hanging Scale Pans (Left & Right)
    var panRadius = 0.72;
    var chainLength = 1.35;

    function buildPanAssembly(armX) {
      var panGroup = new THREE.Group();
      panGroup.position.set(armX, -0.22, 0);

      // Hollow 3D Bowl
      var bowlGeom = new THREE.SphereGeometry(panRadius, 32, 16, 0, Math.PI * 2, Math.PI * 0.44, Math.PI * 0.56);
      var bowlMesh = new THREE.Mesh(bowlGeom, goldBowl);
      bowlMesh.position.y = -chainLength;
      panGroup.add(bowlMesh);

      // Bowl Rim Ring
      var rimMesh = new THREE.Mesh(new THREE.TorusGeometry(panRadius, 0.028, 16, 48), goldPolished);
      rimMesh.position.y = -chainLength;
      rimMesh.rotation.x = Math.PI / 2;
      panGroup.add(rimMesh);

      // 3 Suspension Chains connecting top hook to 3 points around bowl rim
      var topPt = new THREE.Vector3(0, 0, 0);
      for (var i = 0; i < 3; i++) {
        var ang = i * ((Math.PI * 2) / 3);
        var rx = panRadius * Math.cos(ang);
        var rz = panRadius * Math.sin(ang);
        var botPt = new THREE.Vector3(rx, -chainLength, rz);
        panGroup.add(createChain(topPt, botPt, 0.012, goldChain));
      }

      return panGroup;
    }

    var leftPanGroup = buildPanAssembly(-2.15);
    balanceArm.add(leftPanGroup);

    var rightPanGroup = buildPanAssembly(2.15);
    balanceArm.add(rightPanGroup);

    // 5. Ground Contact Shadow
    var shadowCanvas = document.createElement('canvas');
    shadowCanvas.width = 128;
    shadowCanvas.height = 128;
    var sctx = shadowCanvas.getContext('2d');
    var sGrad = sctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    sGrad.addColorStop(0, 'rgba(40, 25, 10, 0.35)');
    sGrad.addColorStop(0.5, 'rgba(180, 131, 62, 0.12)');
    sGrad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    sctx.fillStyle = sGrad;
    sctx.fillRect(0, 0, 128, 128);

    var shadowTexture = new THREE.CanvasTexture(shadowCanvas);
    var shadowPlane = new THREE.Mesh(
      new THREE.PlaneGeometry(3.6, 3.6),
      new THREE.MeshBasicMaterial({ map: shadowTexture, transparent: true, opacity: 0.85 })
    );
    shadowPlane.scale.set(modelScale, modelScale, modelScale);
    shadowPlane.position.y = -1.58 * modelScale;
    shadowPlane.rotation.x = -Math.PI / 2;
    scene.add(shadowPlane);

    // 6. Studio Lighting
    var ambLight = new THREE.AmbientLight(0xfff8f0, 0.72);
    scene.add(ambLight);

    // Key Light (top-front-left)
    var keyLight = new THREE.DirectionalLight(0xfff5e6, 2.3);
    keyLight.position.set(4, 7, 5);
    scene.add(keyLight);

    // Fill Light (mid-front-right)
    var fillLight = new THREE.DirectionalLight(0xddeeff, 1.1);
    fillLight.position.set(-4, 3, 3);
    scene.add(fillLight);

    // Rim Backlight (brilliant golden edge highlights)
    var rimLight = new THREE.DirectionalLight(0xffdf99, 1.9);
    rimLight.position.set(0, 4, -5);
    scene.add(rimLight);

    // 7. Render Loop: Continuous, Rock-Solid In-Place 3D Rotation (ZERO Mouse Dangling)
    var time = 0;

    function animate() {
      requestAnimationFrame(animate);
      time += 0.015;

      // Pure in-place 3D rotation on central vertical Y-axis
      rootGroup.rotation.y += 0.0075;

      // Subtle, realistic equilibrium balance sway on beam (independent of pans)
      var sway = Math.sin(time * 0.9) * 0.022;
      balanceArm.rotation.z = sway;

      // Counter-rotate hanging pans so they remain vertically suspended by gravity
      leftPanGroup.rotation.z = -sway;
      rightPanGroup.rotation.z = -sway;

      renderer.render(scene, camera);
    }

    animate();

    // Resize handling
    window.addEventListener('resize', function () {
      var w = stage.clientWidth || 380;
      var h = stage.clientHeight || 420;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
