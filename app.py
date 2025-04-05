# app.py
import os
import re
import requests
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS # Keep CORS for flexibility
from dotenv import load_dotenv

# Load environment variables (for local .env file testing)
load_dotenv()

# Ensure template_folder='templates' and static_folder='static' are correctly specified
# This tells Flask where to look. These are the defaults but explicit is fine.
app = Flask(__name__, template_folder='templates', static_folder='static')


# --- Initialize CORS ---
CORS(app)

# --- Configuration ---
JIKAN_API_USER_URL = "https://api.jikan.moe/v4/users/{username}/animelist"
WALLHAVEN_API_URL = "https://wallhaven.cc/api/v1/search"
# Get Wallhaven API Key from environment variables (Set this in Render)
WALLHAVEN_API_KEY = os.getenv("WALLHAVEN_API_KEY")
# Number of wallpapers to fetch per anime
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
    text = re.sub(r'\s(2nd season|3rd season|4th season|5th season)', '', text) # Example
    text = re.sub(r'\s[ivx]+$', '', text) # Roman numerals at end
    text = text.replace(':', ' ').replace('-', ' ')
    text = ' '.join(text.split())
    return text.strip()

def get_mal_completed_list(username):
    """ Fetches the completed anime list for a MAL username from Jikan. """
    params = {'status': 'completed', 'sfw': 'true'}
    try:
        response = requests.get(JIKAN_API_USER_URL.format(username=username), params=params, timeout=20)
        response.raise_for_status()
        data = response.json().get('data', [])
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching MAL list for {username}: {e}")
        status_code = getattr(e.response, 'status_code', None)
        if status_code == 404:
             raise ValueError("MAL user not found")
        elif status_code == 429:
             raise ConnectionError("Rate limited by Jikan API. Please wait and try again.")
        raise ConnectionError(f"Could not connect to Jikan API: {e}")
    except Exception as e:
        print(f"An unexpected error occurred fetching MAL list: {e}")
        raise RuntimeError("Internal error processing MAL data")

def group_anime(anime_list):
    """ Groups anime list by cleaned titles. """
    grouped = {}
    for item in anime_list:
        original_title = item.get('anime', {}).get('title', 'Unknown Title')
        mal_id = item.get('anime', {}).get('mal_id', None)
        image_url = item.get('anime', {}).get('images', {}).get('jpg', {}).get('image_url')

        if not original_title or original_title == 'Unknown Title':
            continue
        search_term = original_title
        grouped_key = clean_anime_title(original_title)
        if not grouped_key:
            continue

        if grouped_key not in grouped:
            grouped[grouped_key] = {
                'display_title': original_title,
                'search_term': search_term,
                'mal_ids': set(),
                'image_url': image_url
            }
        if mal_id:
            grouped[grouped_key]['mal_ids'].add(mal_id)
        if len(original_title) < len(grouped[grouped_key]['display_title']):
             grouped[grouped_key]['display_title'] = original_title
             grouped[grouped_key]['image_url'] = image_url
    return grouped

def get_wallpapers(anime_title):
    """ Fetches wallpapers for an anime title from Wallhaven. """
    params = { 'q': anime_title, 'categories': '010', 'purity': '100', 'sorting': 'relevance' }
    headers = {}
    if WALLHAVEN_API_KEY:
        headers['X-API-Key'] = WALLHAVEN_API_KEY
    try:
        response = requests.get(WALLHAVEN_API_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        wallpapers_data = response.json().get('data', [])
        results = []
        for wall in wallpapers_data[:WALLPAPER_LIMIT]:
            thumb = wall.get('thumbs', {}).get('large')
            full_img = wall.get('path')
            if thumb and full_img:
                 results.append({'thumbnail': thumb, 'full': full_img})
        return results
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Wallhaven wallpapers for '{anime_title}': {e}")
        status_code = getattr(e.response, 'status_code', None)
        if status_code == 429: print("Rate limited by Wallhaven API.")
        return []
    except Exception as e:
        print(f"An unexpected error occurred fetching Wallhaven data for '{anime_title}': {e}")
        return []

# --- Routes ---

# This route MUST find 'index.html' inside the 'templates' folder
@app.route('/')
def index():
    """ Serves the main HTML page. """
    print("Attempting to render template 'index.html'") # Add log
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"Error rendering template: {e}") # Log if render_template fails
        raise e


@app.route('/api/wallpapers/<username>')
def get_anime_wallpapers(username):
    """ API endpoint to get grouped anime and wallpapers. """
    if not username: return jsonify({"error": "MAL username is required"}), 400
    try:
        print(f"Fetching MAL list for user: {username}")
        mal_list = get_mal_completed_list(username)
        if not mal_list:
             print(f"No completed anime found for {username}.")
             return jsonify({"message": f"No completed anime found for user '{username}'."}), 404
        print(f"Found {len(mal_list)} completed anime entries. Grouping...")
        grouped_anime = group_anime(mal_list)
        print(f"Grouped into {len(grouped_anime)} unique series.")
        if not grouped_anime:
             return jsonify({"message": f"Could not group any anime for user '{username}'."}), 404
        results = {}
        print("Fetching wallpapers from Wallhaven...")
        processed_count = 0; total_groups = len(grouped_anime)
        for key, data in grouped_anime.items():
            processed_count += 1; print(f"  ({processed_count}/{total_groups}) Searching for: {data['search_term']} (Group: {key})")
            wallpapers = get_wallpapers(data['search_term'])
            if wallpapers:
                 results[key] = { 'display_title': data['display_title'], 'mal_cover': data['image_url'], 'wallpapers': wallpapers }
                 print(f"    -> Found {len(wallpapers)} wallpapers.")
            else: print(f"    -> No wallpapers found.")
        print("Finished fetching wallpapers.")
        if not results:
             return jsonify({"message": "Found completed anime, but no relevant wallpapers could be retrieved from Wallhaven."}), 404
        return jsonify(results)
    except ValueError as e: return jsonify({"error": str(e)}), 404
    except ConnectionError as e: return jsonify({"error": str(e)}), 503
    except RuntimeError as e: return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"An unhandled error occurred in API endpoint: {e}")
        import traceback; traceback.print_exc()
        return jsonify({"error": "An unexpected internal server error occurred"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False) # IMPORTANT: debug=False for production
