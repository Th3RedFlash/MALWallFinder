# app.py
import os
import re
import requests
import traceback # Import traceback for better error logging
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables (for local .env file testing)
load_dotenv()

# Ensure template_folder='templates' and static_folder='static' are correctly specified
app = Flask(__name__, template_folder='templates', static_folder='static')

# --- Initialize CORS ---
CORS(app)

# --- Configuration ---
JIKAN_API_USER_URL = "https://api.jikan.moe/v4/users/{username}/animelist"
WALLHAVEN_API_URL = "https://wallhaven.cc/api/v1/search"
WALLHAVEN_API_KEY = os.getenv("WALLHAVEN_API_KEY") # Set in Render Environment Variables
WALLPAPER_LIMIT = 5

# --- Helper Functions ---

def clean_anime_title(title):
    """ Basic cleaning and grouping of anime titles. """
    text = title.lower()
    text = re.sub(r'\s(season\s?\d+|s\d+)\b', '', text)
    text = re.sub(r'\s(part\s?\d+|p\d+)\b', '', text)
    text = re.sub(r'\s(cour\s?\d+)\b', '', text)
    text = re.sub(r'\s?:\s?(the movie|movie|ova|ona|special|tv special)\b', '', text)
    text = re.sub(r'\s\(\d{4}\)$', '', text)
    text = re.sub(r'\s\(tv\)$', '', text)
    text = re.sub(r'\s(2nd season|3rd season|4th season|5th season)', '', text)
    text = re.sub(r'\s[ivx]+$', '', text)
    text = text.replace(':', ' ').replace('-', ' ')
    text = ' '.join(text.split())
    return text.strip()

# --- UPDATED JIKAN FUNCTION WITH MORE LOGGING ---
def get_mal_completed_list(username):
    """ Fetches the completed anime list for a MAL username from Jikan. """
    params = {'status': 'completed', 'sfw': 'true'}
    request_url = JIKAN_API_USER_URL.format(username=username)
    print(f"  [Jikan] Requesting URL: {request_url} with params: {params}") # Log exact URL
    try:
        response = requests.get(request_url, params=params, timeout=20) # 20 second timeout
        print(f"  [Jikan] Response Status Code: {response.status_code}") # Log status code received

        # Check specific status codes BEFORE raising generic errors
        if response.status_code == 404:
            print(f"  [Jikan] Received 404 for user: {username}. Raising ValueError.")
            # Try to log Jikan's response body for 404 if available
            try:
                error_details = response.json()
                print(f"  [Jikan] 404 Response Body: {error_details}")
            except requests.exceptions.JSONDecodeError:
                print(f"  [Jikan] 404 Response Body: Not valid JSON or empty.")
            raise ValueError("MAL user not found") # Raise specific internal error

        elif response.status_code == 429:
             print(f"  [Jikan] Received 429 Too Many Requests. Raising ConnectionError.")
             raise ConnectionError("Rate limited by Jikan API. Please wait and try again.")

        # Raise HTTPError for other bad responses (4xx client error, 5xx server error)
        response.raise_for_status()

        # If response is OK (2xx)
        data = response.json().get('data', [])
        print(f"  [Jikan] Successfully received data ({len(data)} items) for {username}.")
        return data

    except ValueError as e: # Catch specific "MAL user not found"
        raise e # Re-raise it to be handled by the main endpoint
    except ConnectionError as e: # Catch specific "Rate limited"
        raise e # Re-raise it

    except requests.exceptions.RequestException as e:
        # Log details about other request exceptions (timeout, connection refused, etc.)
        print(f"  [Jikan] RequestException occurred: {type(e).__name__} - {e}")
        response_content = getattr(e.response, 'text', 'No response content available')
        print(f"  [Jikan] Response content (if any): {response_content[:500]}...") # Log first 500 chars
        status_code = getattr(e.response, 'status_code', 'N/A')
        print(f"  [Jikan] Status code (if available): {status_code}")
        # Raise a generic connection error for the API endpoint to catch
        raise ConnectionError(f"Could not connect to Jikan API or API returned an error (Status: {status_code}).")

    except Exception as e:
        # Catch any other unexpected errors during Jikan processing
        print(f"  [Jikan] An unexpected error occurred processing Jikan response: {type(e).__name__} - {e}")
        traceback.print_exc() # Log full traceback for unexpected errors
        raise RuntimeError("Internal error processing MAL data")
# --- END OF UPDATED JIKAN FUNCTION ---

def group_anime(anime_list):
    """ Groups anime list by cleaned titles. """
    grouped = {}
    for item in anime_list:
        original_title = item.get('anime', {}).get('title', 'Unknown Title')
        mal_id = item.get('anime', {}).get('mal_id', None)
        image_url = item.get('anime', {}).get('images', {}).get('jpg', {}).get('image_url')
        if not original_title or original_title == 'Unknown Title': continue
        search_term = original_title
        grouped_key = clean_anime_title(original_title)
        if not grouped_key: continue
        if grouped_key not in grouped:
            grouped[grouped_key] = { 'display_title': original_title, 'search_term': search_term, 'mal_ids': set(), 'image_url': image_url }
        if mal_id: grouped[grouped_key]['mal_ids'].add(mal_id)
        if len(original_title) < len(grouped[grouped_key]['display_title']):
             grouped[grouped_key]['display_title'] = original_title
             grouped[grouped_key]['image_url'] = image_url
    return grouped

def get_wallpapers(anime_title):
    """ Fetches wallpapers for an anime title from Wallhaven. """
    params = { 'q': anime_title, 'categories': '010', 'purity': '100', 'sorting': 'relevance' }
    headers = {}
    if WALLHAVEN_API_KEY: headers['X-API-Key'] = WALLHAVEN_API_KEY
    print(f"    [Wallhaven] Searching for: {anime_title}") # Log Wallhaven search term
    try:
        response = requests.get(WALLHAVEN_API_URL, params=params, headers=headers, timeout=15)
        print(f"    [Wallhaven] Response Status Code: {response.status_code}") # Log Wallhaven status
        response.raise_for_status()
        wallpapers_data = response.json().get('data', [])
        results = []
        for wall in wallpapers_data[:WALLPAPER_LIMIT]:
            thumb = wall.get('thumbs', {}).get('large'); full_img = wall.get('path')
            if thumb and full_img: results.append({'thumbnail': thumb, 'full': full_img})
        print(f"    [Wallhaven] Found {len(results)} wallpapers.") # Log count found
        return results
    except requests.exceptions.RequestException as e:
        print(f"    [Wallhaven] RequestException occurred: {type(e).__name__} - {e}")
        status_code = getattr(e.response, 'status_code', 'N/A')
        if status_code == 429: print("    [Wallhaven] Received 429 Too Many Requests.")
        return [] # Don't stop the whole process for one failed search
    except Exception as e:
        print(f"    [Wallhaven] An unexpected error occurred fetching Wallhaven data: {type(e).__name__} - {e}")
        return []

# --- Routes ---
@app.route('/')
def index():
    """ Serves the main HTML page. """
    print("[Request] Received request for / route")
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"[Error] Error rendering template index.html: {type(e).__name__} - {e}")
        traceback.print_exc()
        raise e

@app.route('/api/wallpapers/<username>')
def get_anime_wallpapers(username):
    """ API endpoint to get grouped anime and wallpapers. """
    print(f"[Request] Received API request for username: {username}")
    if not username: return jsonify({"error": "MAL username is required"}), 400
    try:
        print(f"  [Flow] Fetching MAL list for user: {username}")
        mal_list = get_mal_completed_list(username) # Call updated function

        print(f"  [Flow] Found {len(mal_list)} completed anime entries. Grouping...")
        grouped_anime = group_anime(mal_list)
        print(f"  [Flow] Grouped into {len(grouped_anime)} unique series.")
        if not grouped_anime:
             print("  [Result] No anime could be grouped.")
             return jsonify({"message": f"Could not group any anime for user '{username}'. Check MAL profile visibility or list content."}), 404

        results = {}
        print(f"  [Flow] Fetching wallpapers from Wallhaven for {len(grouped_anime)} groups...")
        processed_count = 0; total_groups = len(grouped_anime)
        for key, data in grouped_anime.items():
            processed_count += 1; print(f"  [Flow] ({processed_count}/{total_groups}) Processing group: {key}")
            wallpapers = get_wallpapers(data['search_term'])
            if wallpapers:
                 results[key] = { 'display_title': data['display_title'], 'mal_cover': data['image_url'], 'wallpapers': wallpapers }

        print("  [Flow] Finished fetching wallpapers.")
        if not results:
             print("  [Result] No wallpapers found for any grouped anime.")
             return jsonify({"message": "Found completed anime, but no relevant wallpapers could be retrieved from Wallhaven."}), 404

        print(f"  [Result] Returning {len(results)} anime groups with wallpapers.")
        return jsonify(results)

    # Handle specific errors raised from helper functions
    except ValueError as e: # MAL User not found
        print(f"[Error] ValueError: {e}")
        return jsonify({"error": str(e)}), 404
    except ConnectionError as e: # Jikan rate limit or connection issue
        print(f"[Error] ConnectionError: {e}")
        return jsonify({"error": str(e)}), 503 # 503 Service Unavailable seems appropriate
    except RuntimeError as e: # Internal processing error
        print(f"[Error] RuntimeError: {e}")
        return jsonify({"error": str(e)}), 500
    # Generic catch-all for anything else
    except Exception as e:
        print(f"[Error] An unhandled error occurred in API endpoint: {type(e).__name__} - {e}")
        traceback.print_exc()
        return jsonify({"error": "An unexpected internal server error occurred"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on host 0.0.0.0, port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
