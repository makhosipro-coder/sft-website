// SFT — Samsung Firmware Tool
// v2.5.0 | Build: 20260615

// Mobile nav toggle
function toggleNav() {
  document.getElementById('navLinks').classList.toggle('open');
}

// Smooth scroll for anchor links
document.querySelectorAll('a[href^="#"]').forEach(function(a) {
  a.addEventListener('click', function(e) {
    var id = a.getAttribute('href');
    if (id === '#') return;
    e.preventDefault();
    var el = document.querySelector(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      document.querySelectorAll('.nav-links a').forEach(function(l) {
        l.classList.remove('active');
      });
      a.classList.add('active');
      document.getElementById('navLinks').classList.remove('open');
    }
  });
});

// ─── Auto-Detection Status Refresh ──────────────────────────────────────

function refreshDeviceStatus() {
  fetch('/api/device/status')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var dot = document.getElementById('headerDot');
      var status = document.getElementById('headerStatus');
      var usbDot = document.getElementById('usbDot');
      var usbStatus = document.getElementById('usbStatus');

      if (data.connected) {
        if (dot) { dot.classList.remove('idle'); dot.classList.add('active'); }
        if (status) {
          var label = data.model || 'Samsung Device';
          if (data.model_name) label += ' (' + data.model_name + ')';
          status.textContent = label;
        }
        if (usbDot) { usbDot.classList.remove('idle'); usbDot.classList.add('active'); }
        if (usbStatus) {
          var mode = data.connection_mode || 'Connected';
          if (data.firmware) mode += ' — ' + data.firmware;
          usbStatus.textContent = mode;
        }
      } else {
        if (dot) { dot.classList.remove('active'); dot.classList.add('idle'); }
        if (status) status.textContent = 'NO DEVICE';
        if (usbDot) { usbDot.classList.remove('active'); usbDot.classList.add('idle'); }
        if (usbStatus) usbStatus.textContent = 'No device detected';
      }
    })
    .catch(function() {
      // Silent fail — device may not be connected
    });
}

// Initial status check
setTimeout(refreshDeviceStatus, 1000);

// Auto-refresh every 5 seconds
setInterval(refreshDeviceStatus, 5000);

// Intersection Observer for scroll animations
var observer = new IntersectionObserver(function(entries) {
  entries.forEach(function(entry) {
    if (entry.isIntersecting) {
      entry.target.classList.add('animate-in');
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.model-card, .reset-card, .step-card').forEach(function(el) {
  el.style.opacity = '0';
  observer.observe(el);
});

console.log('[SFT] Samsung Firmware Tool v2.5.0 initialized');
console.log('[SFT] Auto-detection active — scanning ADB/Fastboot/Heimdall/USB');
console.log('[SFT] Status refresh: 5s interval');
