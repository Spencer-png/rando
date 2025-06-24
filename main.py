from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import os
import logging

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app, origins="*")

@app.before_request
def log_request_info():
    """Logs information about each incoming request."""
    app.logger.info('Request Path: %s', request.path)
    app.logger.info('Request Method: %s', request.method)
    app.logger.info('Request Headers: %s', request.headers)
    if request.data:
        app.logger.info('Request Body: %s', request.data.decode('utf-8'))

@app.route('/api/gemini', methods=['POST'])
def proxy_gemini():
    """
    Proxies requests to the Google Gemini API.
    It now automatically rotates keys if one is rate-limited.
    """
    try:
        data = request.get_json()
        
        api_keys_string = "AIzaSyA3Zhw-Apw21X2AI6cLQWZU7LGttcqhNlE, AIzaSyD6_NumVL4C7_ZcPJF4UsXrGdAlGL8DB3o, AIzaSyBa3HiFNLfROshwL1PiC0sql_-wJRj3wd8, AIzaSyB_yr7UjOn387AdUDII6Va6hXh2tHhaVp0, AIzaSyCLl5NEjSjBbgXViZpO4fVsGQnFJHl31p8"
        api_keys = [key.strip() for key in api_keys_string.split(',')]

        for api_key in api_keys:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
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
        return jsonify({"error": "All Gemini API keys are rate-limited.", "details": "Please try again later or add new keys."}), 429

    except Exception as e:
        app.logger.error(f"An unexpected error occurred in proxy_gemini: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/claude', methods=['POST'])
def proxy_claude():
    """
    Proxies requests to the Anthropic Claude API.
    """
    try:
        data = request.get_json()
        api_key = data.get('api_key', 'sk-ant-api03-YOUR_CLAUDE_KEY_HERE')
        
        if 'YOUR_CLAUDE_KEY_HERE' in api_key:
            return jsonify({"error": "Claude API key not configured"}), 400
        
        api_url = "https://api.anthropic.com/v1/messages"
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01'
        }
        
        payload = {
            "model": data.get('model', 'claude-3-opus-20240229'),
            "max_tokens": data.get('max_tokens', 1024),
            "messages": data.get('messages', [])
        }
        
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        
        return jsonify(response.json())

    except requests.exceptions.HTTPError as http_err:
        app.logger.error(f"HTTP error occurred while contacting Claude: {http_err}")
        app.logger.error(f"Claude Response body: {response.text}")
        return jsonify({"error": "Claude API error", "details": response.text}), response.status_code
    except Exception as e:
        app.logger.error(f"An unexpected error occurred in proxy_claude: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/openai', methods=['POST'])
def proxy_openai():
    """
    Proxies requests to the OpenAI API.
    """
    try:
        data = request.get_json()
        api_key = data.get('api_key', 'sk-proj-YOUR_OPENAI_KEY_HERE')
        
        if 'YOUR_OPENAI_KEY_HERE' in api_key:
            return jsonify({"error": "OpenAI API key not configured"}), 400
        
        api_url = "https://api.openai.com/v1/chat/completions"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        
        payload = {
            "model": data.get('model', 'gpt-4'),
            "messages": data.get('messages', []),
            "max_tokens": data.get('max_tokens', 1024),
            "temperature": data.get('temperature', 0.7)
        }
        
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        
        return jsonify(response.json())

    except requests.exceptions.HTTPError as http_err:
        app.logger.error(f"HTTP error occurred while contacting OpenAI: {http_err}")
        app.logger.error(f"OpenAI Response body: {response.text}")
        return jsonify({"error": "OpenAI API error", "details": response.text}), response.status_code
    except Exception as e:
        app.logger.error(f"An unexpected error occurred in proxy_openai: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/manus', methods=['POST'])
def proxy_manus():
    """
    A mock endpoint for Manus AI.
    """
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        response_text = f"Manus AI Response: Based on the task \"{prompt[:100]}...\", I would recommend creating a comprehensive solution using the Perception.cx API. This would involve implementing the requested functionality with proper error handling and optimization."
        
        return jsonify({"response": response_text})
    except Exception as e:
        app.logger.error(f"An error occurred in manus proxy: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint to confirm the service is running.
    """
    return jsonify({"status": "healthy", "service": "AI Proxy Backend"})

if __name__ == '__main__':
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    app.run(host=host, port=port, debug=debug)
