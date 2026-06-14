"""
Netlify Serverless Function — Flask Wrapper
Handles all Flask routes via Netlify Functions
"""

import os
import sys
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def handler(event, context):
    """Netlify Function handler."""
    path = event.get('path', '/').lstrip('/')
    method = event.get('httpMethod', 'GET')
    query = event.get('queryStringParameters') or {}
    body = event.get('body', '')
    
    # API routes
    if path.startswith('api/'):
        return handle_api(path, method, query, body)
    
    # Static files
    if path.startswith('static/'):
        return serve_static(path)
    
    # Default: return index
    return {
        'statusCode': 200,
        'headers': {'Content-Type': 'text/html'},
        'body': get_index_html()
    }

def handle_api(path, method, query, body):
    """Handle API routes."""
    if path == 'api/device/status':
        return json_response({
            'connected': False,
            'model': '',
            'platform': 'netlify',
            'note': 'Device detection requires local USB access. Run locally for full functionality.'
        })
    
    if path == 'api/device/models':
        # Return model database
        models = {
            'SM-S928B': {'chipset': 'Snapdragon 8 Gen 3', 'series': 'S24 Ultra'},
            'SM-A042F': {'chipset': 'Helio G85', 'series': 'A04e'},
            'SM-A546B': {'chipset': 'Exynos 1380', 'series': 'A54 5G'},
            'SM-A556B': {'chipset': 'Exynos 1480', 'series': 'A55 5G'},
        }
        return json_response({'models': models})
    
    return json_response({'error': 'Unknown endpoint'}, 404)

def serve_static(path):
    """Serve static files."""
    try:
        static_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), path)
        if os.path.exists(static_path):
            content_type = 'text/css' if path.endswith('.css') else 'application/javascript'
            with open(static_path, 'r') as f:
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': content_type},
                    'body': f.read()
                }
    except Exception:
        pass
    return {'statusCode': 404, 'body': 'Not found'}

def json_response(data, status=200):
    """Return JSON response."""
    return {
        'statusCode': status,
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps(data)
    }

def get_index_html():
    """Return the main index page."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SFT — Samsung Firmware Tool</title>
<style>
body{font-family:system-ui,sans-serif;background:#0a1628;color:#e2e8f0;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0}
.card{background:#132744;border:1px solid #1e3a5f;border-radius:8px;padding:2rem;max-width:400px;text-align:center}
h1{font-size:1.2rem;margin-bottom:.5rem}
p{color:#94a3b8;font-size:.85rem;line-height:1.6}
a{color:#6db3f2}
</style>
</head>
<body>
<div class="card">
<h1>🔧 SFT — Samsung Firmware Tool</h1>
<p>v2.5.0 — Hosted on Netlify</p>
<p style="margin-top:1rem">For full device detection and USB functionality, run the tool locally:</p>
<pre style="background:#0a1628;padding:.75rem;border-radius:4px;font-size:.72rem;text-align:left;margin-top:.5rem">git clone https://github.com/sprutting/sft-website.git
cd sft-website
pip3 install flask
python3 app.py</pre>
<p style="margin-top:1rem;font-size:.72rem">Then open <a href="http://localhost:5000">localhost:5000</a></p>
</div>
</body>
</html>'''
