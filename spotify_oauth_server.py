import os 
from flask import Flask, request, redirect, render_template
from urllib.parse import urlencode
import requests
from dotenv import load_dotenv
from token_store import save_token, get_token
import logging
import base64

load_dotenv()

logging.basicConfig(level=logging.DEBUG)


app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecret")

SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8080/callback")
SPOTIFY_SCOPE         = "user-read-playback-state user-modify-playback-state"


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login():
    user_id = request.args.get("user_id")
    if not user_id:
        return "Missing User ID", 400
    
    params = {
        'client_id':     SPOTIFY_CLIENT_ID,
        'response_type': 'code',
        'redirect_uri':  SPOTIFY_REDIRECT_URI,
        'scope':         SPOTIFY_SCOPE,
        'state':         user_id,
        'show_dialog':   'true'
    }
    auth_url = "https://accounts.spotify.com/authorize?" + urlencode(params)

    return redirect(auth_url)

@app.route("/callback")
def callback():
    code  = request.args.get("code")
    state = request.args.get("state")
    if not code or not state:
        return "Invalid callback parameters", 400

    # Prepare token exchange
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        'grant_type':   'authorization_code',
        'code':         code,
        'redirect_uri': SPOTIFY_REDIRECT_URI
    }
    creds = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    b64creds = base64.b64encode(creds.encode()).decode()
    headers = {
        'Authorization': f'Basic {b64creds}',
        'Content-Type':  'application/x-www-form-urlencoded'
    }

    # Perform exchange
    resp = requests.post(token_url, data=payload, headers=headers)
    logging.debug(f"▶️ Spotify token exchange status: {resp.status_code}")
    logging.debug(f"▶️ Spotify response body: {resp.text}")

    token_info = resp.json()
    if 'access_token' in token_info:
        save_token(state, token_info)
        return render_template("success.html", user=state)
    else:
        return render_template("failure.html"), 400
    

@app.route("/health")
def health():
    """Simple health check endpoint."""
    return "OK", 200

if __name__ == "__main__":
    # Start the OAuth server on port 8888
    app.run(host="0.0.0.0", port=8080, debug=True)
