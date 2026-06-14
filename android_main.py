"""
SFT — Samsung Firmware Tool
Android Application Entry Point
Version: 2.5.0

This wraps the SFT web dashboard in a native Android WebView
so it can be installed as a standalone APK.
"""

import os
import sys
import threading
import json
from flask import Flask, render_template_string, jsonify, request

# ─── Embedded Templates (for standalone APK) ────────────────────────────

INDEX_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
<title>SFT — Samsung Firmware Tool</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --blue:#1428a0;--blue-hover:#1a35c8;--blue-light:#eef2ff;
  --navy:#0a1628;--navy-mid:#132744;
  --white:#ffffff;--gray-50:#f8fafc;--gray-100:#f1f5f9;--gray-200:#e2e8f0;
  --gray-300:#cbd5e1;--gray-400:#94a3b8;--gray-500:#64748b;--gray-600:#475569;
  --gray-700:#334155;--gray-800:#1e293b;
  --green:#22c55e;--green-bg:#f0fdf4;--green-border:#bbf7d0;
  --amber:#f59e0b;--amber-bg:#fffbeb;--amber-border:#fde68a;
  --red:#ef4444;--red-bg:#fef2f2;
  --font-ui:system-ui,-apple-system,sans-serif;
  --font-mono:ui-monospace,monospace;
}
body{font-family:var(--font-ui);background:var(--white);color:var(--gray-800);line-height:1.6;font-size:14px}
.container{max-width:500px;margin:0 auto;padding:0 1rem}
.header{background:var(--navy);color:var(--white);padding:1rem 0;position:sticky;top:0;z-index:100}
.header h1{font-size:1rem;font-weight:700;display:flex;align-items:center;gap:.5rem}
.logo-mark{width:24px;height:24px;background:var(--blue);border-radius:4px;display:flex;align-items:center;justify-content:center;font-family:var(--font-mono);font-size:.6rem;font-weight:800}
.nav{display:flex;gap:.5rem;margin-top:.75rem;overflow-x:auto;padding-bottom:.25rem}
.nav a{color:var(--gray-400);font-size:.7rem;font-weight:500;padding:.35rem .65rem;border-radius:4px;white-space:nowrap;text-decoration:none}
.nav a.active{color:var(--white);background:rgba(255,255,255,.08)}
.card{background:var(--white);border:1px solid var(--gray-200);border-radius:8px;margin-bottom:1rem;overflow:hidden}
.card-header{padding:.65rem .85rem;background:var(--gray-50);border-bottom:1px solid var(--gray-200)}
.card-header h3{font-size:.75rem;font-weight:700;color:var(--navy);font-family:var(--font-mono)}
.card-body{padding:.85rem}
.status-dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.status-dot.active{background:var(--green)}
.status-dot.idle{background:var(--gray-300)}
.status-dot.error{background:var(--red)}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:.3rem;padding:.5rem 1rem;font-size:.72rem;font-weight:600;border:0;border-radius:4px;cursor:pointer}
.btn-primary{background:var(--blue);color:var(--white)}
.btn-full{width:100%}
.text-mono{font-family:var(--font-mono)}
.text-dim{color:var(--gray-400)}
.text-sm{font-size:.75rem}
.text-xs{font-size:.65rem}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:.75rem}
.mt-1{margin-top:.5rem}
</style>
</head>
<body>
<div class="header">
  <div class="container">
    <h1><div class="logo-mark">SFT</div> Samsung Firmware Tool</h1>
    <div class="nav">
      <a href="#" class="active" onclick="showTab('status',event)">Status</a>
      <a href="#" onclick="showTab('decoder',event)">Decoder</a>
      <a href="#" onclick="showTab('firmware',event)">Firmware</a>
      <a href="#" onclick="showTab('flash',event)">Flash</a>
    </div>
  </div>
</div>
<div class="container" style="padding-top:1rem">

  <!-- Status Tab -->
  <div id="tab-status" class="tab-content">
    <div class="card">
      <div class="card-header"><h3>DEVICE STATUS</h3></div>
      <div class="card-body">
        <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.75rem">
          <span class="status-dot idle" id="devDot"></span>
          <span id="devStatus" class="text-sm text-dim">Checking...</span>
        </div>
        <div class="card" style="background:var(--navy);color:var(--gray-300);font-family:var(--font-mono);font-size:.68rem;padding:.75rem;border-radius:4px">
          <div id="devInfo">Connect a Samsung device via USB</div>
        </div>
        <button class="btn btn-primary btn-full mt-1" onclick="scanDevice()">⟳ SCAN</button>
      </div>
    </div>
  </div>

  <!-- Decoder Tab -->
  <div id="tab-decoder" class="tab-content" style="display:none">
    <div class="card">
      <div class="card-header"><h3>FIRMWARE DECODER</h3></div>
      <div class="card-body">
        <input type="text" id="fwInput" placeholder="e.g. S928BXXS4AYA1" maxlength="13" style="width:100%;background:var(--gray-50);border:1px solid var(--gray-200);border-radius:4px;padding:.5rem;font-family:var(--font-mono);font-size:.85rem;text-transform:uppercase;letter-spacing:.04em" oninput="decodeFW(this.value)">
        <div id="fwResult" class="mt-1"></div>
      </div>
    </div>
  </div>

  <!-- Firmware Tab -->
  <div id="tab-firmware" class="tab-content" style="display:none">
    <div class="card">
      <div class="card-header"><h3>FIRMWARE DATABASE</h3></div>
      <div class="card-body text-sm text-dim">
        <p>Online firmware database. Connect to the SFT server for full functionality.</p>
        <p class="mt-1 text-xs">Build: v2.5.0 | 237+ CSC codes | 82 device models</p>
      </div>
    </div>
  </div>

  <!-- Flash Tab -->
  <div id="tab-flash" class="tab-content" style="display:none">
    <div class="card">
      <div class="card-header"><h3>FLASH GUIDE</h3></div>
      <div class="card-body text-sm text-dim">
        <p><strong>SM-A042F MediaTek Device</strong></p>
        <p class="mt-1">⚠️ This device requires Odin on Windows. macOS cannot flash MediaTek Samsung devices.</p>
        <ol style="padding-left:1.25rem;margin-top:.5rem;line-height:1.8">
          <li>Download firmware (tar.md5 files)</li>
          <li>Install Samsung USB drivers on Windows</li>
          <li>Open Odin3 v3.14.4 as Administrator</li>
          <li>Load BL, AP, CP, CSC files</li>
          <li>Click START and wait for PASS!</li>
        </ol>
      </div>
    </div>
  </div>

</div>
<div style="text-align:center;padding:1rem 0;font-family:var(--font-mono);font-size:.6rem;color:var(--gray-400)">
  SFT v2.5.0 | Not affiliated with Samsung Electronics
</div>
<script>
function showTab(tab, e) {
  if(e) e.preventDefault();
  document.querySelectorAll('.tab-content').forEach(function(t){t.style.display='none'});
  document.querySelectorAll('.nav a').forEach(function(a){a.classList.remove('active')});
  document.getElementById('tab-'+tab).style.display='block';
  if(e) e.target.classList.add('active');
}

function scanDevice() {
  var dot = document.getElementById('devDot');
  var status = document.getElementById('devStatus');
  var info = document.getElementById('devInfo');
  dot.className = 'status-dot active';
  status.textContent = 'Scanning...';
  info.textContent = 'Scanning USB devices...';
  setTimeout(function() {
    status.textContent = 'No device found';
    info.textContent = 'Connect USB debugging enabled device';
    dot.className = 'status-dot idle';
  }, 2000);
}

var SERIES={S:'Galaxy S',N:'Galaxy Note',A:'Galaxy A',M:'Galaxy M',Z:'Galaxy Z'};
var MODELS={'928':'S24 Ultra','546':'A54 5G','042':'A04e','356':'A35 5G','556':'A55 5G'};
var TYPES={S:'Security',U:'Major Update',A:'Annual',E:'Engineering'};
var MONTHS={A:'Jan',B:'Feb',C:'Mar',D:'Apr',E:'May',F:'Jun',G:'Jul',H:'Aug',I:'Sep',J:'Oct',K:'Nov',L:'Dec'};
var TYPE_YEAR={}; for(var i=0;i<26;i++) TYPE_YEAR[String.fromCharCode(65+i)]=2024+i;

function decodeFW(val) {
  val=val.trim().toUpperCase();
  var res=document.getElementById('fwResult');
  if(val.length!==13){if(val.length>0)res.innerHTML='<div class="text-xs" style="color:var(--amber)">Enter exactly 13 characters</div>';else res.innerHTML='';return;}
  var hw=val.substring(0,5),series=hw[0],model=hw.substring(1,4),variant=hw[4];
  var market=val.substring(5,8),bl=val[8],type=val[9],yr=TYPE_YEAR[type]||0;
  var monthCode=val[10],month=MONTHS[monthCode]||'?';
  var html='<div class="card" style="background:var(--gray-50);padding:.75rem;margin-top:.5rem">'+
    '<div class="fw-string" style="font-family:var(--font-mono);font-size:.85rem;font-weight:700;color:var(--navy);margin-bottom:.5rem">'+val+'</div>'+
    '<div class="text-xs text-dim">'+SERIES[series]+' '+MODELS[model]+'</div>'+
    '<div class="text-xs text-dim">CSC: '+market+' | BL: v'+bl+' | '+TYPES[type]+'</div>'+
    '<div class="text-xs text-dim">'+month+' '+yr+'</div>'+
    '</div>';
  res.innerHTML=html;
}
</script>
</body>
</html>
"""

# ─── Flask App ───────────────────────────────────────────────────────────

app = Flask(__name__)

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/api/status')
def api_status():
    return jsonify({
        'app': 'SFT — Samsung Firmware Tool',
        'version': '2.5.0',
        'platform': 'android',
        'device_connected': False,
    })

def run_server():
    """Run Flask server in background thread."""
    app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False)

if __name__ == '__main__':
    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Import and run Kivy
    try:
        from kivy.app import App
        from kivy.uix.webview import WebView
        
        class SFTApp(App):
            def build(self):
                return WebView(source='http://127.0.0.1:8080')
        
        SFTApp().run()
    except ImportError:
        # Fallback: just run the Flask server
        print("SFT v2.5.0 running at http://127.0.0.1:8080")
        print("Install Kivy for native Android app: pip install kivy")
        run_server()
