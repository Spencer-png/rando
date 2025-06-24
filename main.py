from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
import logging
from dotenv import load_dotenv

# Load environment variables from a .env file for local development.
# This line is not strictly necessary for Render but is good practice.
load_dotenv() 

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
# For production, it's better to restrict origins to your specific frontend URL
# Example: CORS(app, origins=["https://your-frontend-app.onrender.com"])
CORS(app, origins="*")

@app.before_request
def log_request_info():
    """Logs information about each incoming request."""
    # Consider reducing log verbosity in a high-traffic production environment.
    app.logger.info('Request Path: %s', request.path)
    app.logger.info('Request Method: %s', request.method)
    if request.data:
        app.logger.info('Request Body: %s', request.data.decode('utf-8'))

@app.route('/api/gemini', methods=['POST'])
def proxy_gemini():
    """
    Proxies requests to the Google Gemini API, using environment variables for keys.
    """
    try:
        data = request.get_json()
        
        # --- CORRECT: Load keys securely from an environment variable ---
        # In Render, you will set an environment variable named GEMINI_API_KEYS
        # with your comma-separated keys.
        api_keys_string = os.environ.get("GEMINI_API_KEYS")
        if not api_keys_string:
            app.logger.error("GEMINI_API_KEYS environment variable not set on the server.")
            return jsonify({"error": "Server is not configured with API keys."}), 500
            
        api_keys = [key.strip() for key in api_keys_string.split(',')]

        for api_key in api_keys:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            app.logger.info(f"Attempting request to Gemini with key ending in ...{api_key[-4:]}")
            
            response = requests.post(api_url, json=data, headers={'Content-Type': 'application/json'})
            
            if response.status_code == 200:
                app.logger.info(f"Request successful with key ...{api_key[-4:]}")
                return jsonify(response.json())
            
            if response.status_code == 429:
                app.logger.warning(f"Key ...{api_key[-4:]} is rate-limited (429). Trying next key.")
                continue
            
            app.logger.error(f"Non-429 HTTP error with key ...{api_key[-4:]}: {response.status_code}")
            app.logger.error(f"Gemini Response Body: {response.text}")
            return jsonify({"error": "Gemini API error", "details": response.text}), response.status_code
        
        app.logger.error("All available Gemini API keys are rate-limited.")
        return jsonify({"error": "All Gemini API keys are rate-limited."}), 429

    except Exception as e:
        app.logger.error(f"An unexpected error occurred in proxy_gemini: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/claude', methods=['POST'])
def proxy_claude():
    """ Proxies requests to the Anthropic Claude API. """
    try:
        data = request.get_json()
        # Load key from environment variable
        api_key = os.environ.get("CLAUDE_API_KEY", 'sk-ant-api03-YOUR_CLAUDE_KEY_HERE')
        
        if 'YOUR_CLAUDE_KEY_HERE' in api_key:
            return jsonify({"error": "Claude API key not configured on the server"}), 400
        
        api_url = "https://api.anthropic.com/v1/messages"
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01'
        }
        
        payload = { "model": "claude-3-opus-20240229", "max_tokens": 1024, "messages": data.get('messages', []) }
        
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())

    except requests.exceptions.HTTPError as http_err:
        app.logger.error(f"HTTP error occurred while contacting Claude: {http_err}")
        return jsonify({"error": "Claude API error", "details": response.text}), response.status_code
    except Exception as e:
        app.logger.error(f"An error occurred in proxy_claude: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/openai', methods=['POST'])
def proxy_openai():
    """ Proxies requests to the OpenAI API. """
    try:
        data = request.get_json()
        # Load key from environment variable
        api_key = os.environ.get("OPENAI_API_KEY", 'sk-proj-YOUR_OPENAI_KEY_HERE')
        
        if 'YOUR_OPENAI_KEY_HERE' in api_key:
            return jsonify({"error": "OpenAI API key not configured on the server"}), 400
        
        api_url = "https://api.openai.com/v1/chat/completions"
        headers = { 'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}' }
        payload = { "model": "gpt-4", "messages": data.get('messages', []), "max_tokens": 1024 }
        
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        return jsonify(response.json())

    except requests.exceptions.HTTPError as http_err:
        app.logger.error(f"HTTP error occurred while contacting OpenAI: {http_err}")
        return jsonify({"error": "OpenAI API error", "details": response.text}), response.status_code
    except Exception as e:
        app.logger.error(f"An error occurred in proxy_openai: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/manus', methods=['POST'])
def proxy_manus():
    """ A mock endpoint for Manus AI. """
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        response_text = f"Manus AI Response: Based on the task \"{prompt[:100]}...\", I would recommend creating a comprehensive solution using the Perception.cx API."
        return jsonify({"response": response_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """ Health check endpoint to confirm the service is running. """
    return jsonify({"status": "healthy"})

# This block is for local development only and will not be used by Render/Gunicorn
if __name__ == '__main__':
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(host=host, port=port, debug=debug)
