# app.py
import os
import re
import requests
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv

# Load environment variables (optional, for API key)
load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')

# --- Configuration ---
JIKAN_API_USER_URL = "https://api.jikan.moe/v4/users/{username}/animelist"
WALLHAVEN_API_URL = "https://wallhaven.cc/api/v1/search"
# Get Wallhaven API Key from environment variables if available
WALLHAVEN_API_KEY = os.getenv("WALLHAVEN_API_KEY")
# Number of wallpapers to fetch per anime
WALLPAPER_LIMIT = 5

# --- Helper Functions ---

def clean_anime_title(title):
    """ Basic cleaning and grouping of anime titles. """
    # Lowercase
    text = title.lower()
    # Remove common season/part indicators
    text = re.sub(r'\s(season\s?\d+|s\d+)\b', '', text)
    text = re.sub(r'\s(part\s?\d+|p\d+)\b', '', text)
    text = re.sub(r'\s(cour\s?\d+)\b', '', text)
    # Remove specific types often appended
    text = re.sub(r'\s?:\s?(the movie|movie|ova|ona|special|tv special)\b', '', text)
    # Remove year in parentheses at the end, e.g., (2023)
    text = re.sub(r'\s\(\d{4}\)$', '', text)
    # Remove (TV) suffix
    text = re.sub(r'\s\(tv\)$', '', text)
    # Specific common sequel indicators (can be expanded)
    text = re.sub(r'\s(2nd season|3rd season|4th season|5th season)', '', text) # Example
    text = re.sub(r'\s[ivx]+$', '', text) # Roman numerals at end
    # Replace common separators with spaces
    text = text.replace(':', ' ').replace('-', ' ')
    # Normalize whitespace
    text = ' '.join(text.split())
    return text.strip()

def get_mal_completed_list(username):
    """ Fetches the completed anime list for a MAL username from Jikan. """
    params = {
        'status': 'completed',
        'sfw': 'true', # Filter for Safe-for-Work titles on MAL side if needed
        # Jikan defaults to 25 per page, handle pagination for large lists if necessary
        # 'page': 1
    }
    try:
        response = requests.get(JIKAN_API_USER_URL.format(username=username), params=params, timeout=15)
        response.raise_for_status() # Raises HTTPError for bad responses (4XX, 5XX)
        return response.json().get('data', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching MAL list for {username}: {e}")
        if response.status_code == 404:
             raise ValueError("MAL user not found")
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

        # Use the main title as the primary search term before cleaning for grouping
        search_term = original_title
        # Generate a simpler key for grouping similar seasons/parts
        grouped_key = clean_anime_title(original_title)

        if grouped_key not in grouped:
            grouped[grouped_key] = {
                'display_title': original_title, # Show the most representative original title
                'search_term': search_term, # Term to use for Wallhaven
                'mal_ids': set(),
                'image_url': image_url # Store one representative image
            }
        # Keep track of MAL IDs associated with this group
        if mal_id:
            grouped[grouped_key]['mal_ids'].add(mal_id)
        # Update display title logic if needed (e.g., prefer shorter titles)
        if len(original_title) < len(grouped[grouped_key]['display_title']):
             grouped[grouped_key]['display_title'] = original_title
             grouped[grouped_key]['image_url'] = image_url # Update image too
             # Decide if search term should also update (maybe not)

    # Convert mal_ids set back to list for JSON compatibility if needed later
    # for key in grouped:
    #    grouped[key]['mal_ids'] = list(grouped[key]['mal_ids'])

    return grouped

def get_wallpapers(anime_title):
    """ Fetches wallpapers for an anime title from Wallhaven. """
    params = {
        'q': anime_title,
        'categories': '010',  # Anime category only
        'purity': '100',      # SFW only
        'sorting': 'relevance', # relevance, toplist, latest, random
        # 'topRange': '1 M',   # If using toplist sorting
    }
    if WALLHAVEN_API_KEY:
        params['apikey'] = WALLHAVEN_API_KEY

    try:
        response = requests.get(WALLHAVEN_API_URL, params=params, timeout=10)
        response.raise_for_status()
        wallpapers_data = response.json().get('data', [])

        results = []
        for wall in wallpapers_data[:WALLPAPER_LIMIT]: # Limit results
             # Use large thumbnail for preview, path for full image link
            thumb = wall.get('thumbs', {}).get('large')
            full_img = wall.get('path')
            if thumb and full_img:
                 results.append({'thumbnail': thumb, 'full': full_img})
        return results

    except requests.exceptions.RequestException as e:
        print(f"Error fetching Wallhaven wallpapers for '{anime_title}': {e}")
        # Don't crash the whole process, just return empty list for this anime
        return []
    except Exception as e:
        print(f"An unexpected error occurred fetching Wallhaven data: {e}")
        return []

# --- Routes ---

@app.route('/')
def index():
    """ Serves the main HTML page. """
    return render_template('index.html')

@app.route('/api/wallpapers/<username>')
def get_anime_wallpapers(username):
    """ API endpoint to get grouped anime and wallpapers. """
    if not username:
        return jsonify({"error": "MAL username is required"}), 400

    try:
        print(f"Fetching MAL list for user: {username}")
        mal_list = get_mal_completed_list(username)
        if not mal_list:
             # Could be empty list or actual error handled in get_mal_completed_list
             # Assuming empty list means no completed anime found for a valid user
             print(f"No completed anime found for {username} or Jikan error occurred.")
             # Check if the user actually exists separately if needed
             return jsonify({"message": f"No completed anime found for user '{username}' or user does not exist."}), 404

        print(f"Found {len(mal_list)} completed anime entries. Grouping...")
        grouped_anime = group_anime(mal_list)
        print(f"Grouped into {len(grouped_anime)} unique series.")

        results = {}
        # Fetch wallpapers for each group
        # Consider making these calls asynchronous for better performance if list is large
        print("Fetching wallpapers from Wallhaven...")
        count = 0
        for key, data in grouped_anime.items():
            count += 1
            print(f"  ({count}/{len(grouped_anime)}) Searching for: {data['search_term']} (Group: {key})")
            wallpapers = get_wallpapers(data['search_term'])
            if wallpapers: # Only include anime with found wallpapers
                 results[key] = {
                      'display_title': data['display_title'],
                      'mal_cover': data['image_url'], # Add MAL cover
                      'wallpapers': wallpapers
                 }
            else:
                 print(f"    -> No wallpapers found.")
        
        print("Finished fetching wallpapers.")
        if not results:
             return jsonify({"message": "Found completed anime, but no wallpapers could be retrieved from Wallhaven for these titles."}), 200 # Or 404? 200 seems ok.

        return jsonify(results)

    except ValueError as e: # Specific error for User Not Found
        return jsonify({"error": str(e)}), 404
    except ConnectionError as e: # Specific error for connection issues
         return jsonify({"error": str(e)}), 503 # Service Unavailable
    except RuntimeError as e: # Specific error for internal processing
         return jsonify({"error": str(e)}), 500
    except Exception as e:
        # Generic catch-all
        print(f"An unhandled error occurred: {e}")
        return jsonify({"error": "An internal server error occurred"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    # Use environment variable for port if available (for Render), otherwise default to 5000
    port = int(os.environ.get('PORT', 5000))
    # Set debug=False for production on Render
    app.run(host='0.0.0.0', port=port, debug=False)
