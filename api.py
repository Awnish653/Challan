from flask import Flask, request, jsonify, Response
import requests

app = Flask(__name__)

UPSTREAM_BASE = "https://restapi.vahandetails.com/api/vehicles/search"

# Headers exactly as captured from the real request
FORWARD_HEADERS = {
    "Host": "restapi.vahandetails.com",
    "Connection": "keep-alive",
    "sec-ch-ua-platform": '"Android"',
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 16; moto g57 power Build/W1WAAS36.48-12-40-1; wv) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.46 Mobile Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "sec-ch-ua": '"Not;A=Brand";v="8", "Chromium";v="150", "Android WebView";v="150"',
    "sec-ch-ua-mobile": "?1",
    "Origin": "https://vahandetails.com",
    "X-Requested-With": "mark.via.gp",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://vahandetails.com/",
    # We DO NOT send Accept-Encoding for Brotli – requests will handle gzip/deflate automatically,
    # and we’ll always return decompressed JSON to your users.
    "Accept-Language": "en-IN,en-US;q=0.9,en;q=0.8",
}


@app.route("/api/vehicles/search")
def proxy_vehicle_search():
    rc_regn_no = request.args.get("rc_regn_no")
    if not rc_regn_no:
        return jsonify({"success": False, "message": "Missing rc_regn_no parameter"}), 400

    target_url = f"{UPSTREAM_BASE}?rc_regn_no={rc_regn_no}"

    try:
        # Forward the request to the upstream API
        upstream_resp = requests.get(
            target_url,
            headers=FORWARD_HEADERS,
            timeout=15,
            # requests automatically decompresses gzip/deflate, so we get raw JSON
        )
        upstream_resp.raise_for_status()
    except requests.RequestException as e:
        return jsonify({"success": False, "message": f"Upstream error: {str(e)}"}), 502

    # Build a Flask response – ignore hop‑by‑hop headers
    excluded_headers = {
        "content-encoding",
        "content-length",
        "transfer-encoding",
        "connection",
        "keep-alive",
    }
    response_headers = {}
    for key, value in upstream_resp.headers.items():
        if key.lower() not in excluded_headers:
            response_headers[key] = value

    # Ensure we serve as JSON (the upstream did)
    response_headers["Content-Type"] = "application/json; charset=utf-8"

    # Add CORS so your own frontend can call this proxy from anywhere
    response_headers["Access-Control-Allow-Origin"] = "*"
    response_headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response_headers["Access-Control-Allow-Headers"] = "*"

    return Response(
        upstream_resp.content,
        status=upstream_resp.status_code,
        headers=response_headers,
    )


# Optional: health check
@app.route("/")
def index():
    return "Proxy is running. Use /api/vehicles/search?rc_regn_no=..."


if __name__ == "__main__":
    # For development only – use a proper WSGI server (gunicorn) in production
    app.run(host="0.0.0.0", port=5000, debug=True)
