import os
import re
import time
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from jikanpy import Jikan

# --- Configuration ---
# Get Wallhaven API Key from environment variable for security
# You will set this up in Render later.
WALLHAVEN_API_KEY = os.environ.get('WALLHAVEN_API_KEY', None)
WALLHAVEN_API_URL = "https://wallhaven.cc/api/v1/search"
# Be polite to APIs - replace with your actual contact if deploying publicly
USER_AGENT = "MAL_Wallhaven_App/1.0 (Contact: your_email@example.com)"

# --- Flask App Setup ---
app = Flask(__name__)
# Allows requests from your frontend (update '*' to your specific frontend URL in production for better security)
CORS(app)
jikan = Jikan()

# --- Helper Functions ---

def sanitize_anime_title(title):
    """
    Attempts to extract a base anime title for searching Wallhaven.
    This is a simplified version and might need improvement for edge cases.
    """
    # Lowercase for easier matching
    lower_title = title.lower()

    # Remove common season/part indicators and surrounding punctuation/spaces
    # Improved patterns slightly
    patterns_to_remove = [
        r':.*', # Remove everything after a colon (often specifies season/arc) FIRST
        r'\b(season|s)\s?\d+\b', # Season 1, S2, Season2
        r'\bpart\s?\d+\b', # Part 1, Part1
        r'\bpt\.?\s?\d+\b', # Pt. 1, Pt 1
        r'\b\d+(st|nd|rd|th)\s+season\b', # 2nd Season
        r'\bfinal\s+season\b', # Final Season
        r'\b(tv|ova|ona|movie|special)\b', # Type indicators
        r'\s+\(.*?\)', # Remove content inside parentheses at the end of string often
        r'\s+\[.*?\]', # Remove content inside brackets at the end of string
        r'^\s*the\s+', # Remove leading 'the '
    ]

    base_title = lower_title
    for pattern in patterns_to_remove:
        base_title = re.sub(pattern, '', base_title, flags=re.IGNORECASE).strip()

    # Basic cleanup
    base_title = re.sub(r'\s+', ' ', base_title).strip(' -:—') # Replace multiple spaces, trim trailing junk

    # If removing everything left an empty string, revert to original (maybe it was just "Movie")
    if not base_title:
        return title.strip()

    # Prioritize known franchises if possible (simple examples)
    if 'shingeki no kyojin' in lower_title or 'attack on titan' in lower_title:
        return 'Attack on Titan'
    if 'kimetsu no yaiba' in lower_title or 'demon slayer' in lower_title:
         return 'Demon Slayer Kimetsu no Yaiba'
    # Add more specific rules here if needed

    # Capitalize nicely
    return ' '.join(word.capitalize() for word in base_title.split()).strip()


def group_anime(anime_list):
    """Groups anime list by sanitized base title."""
    grouped = {}
    titles_processed = set() # Using MAL ID to track processed items

    if not anime_list: # Handle empty list case
        return grouped

    for anime_entry in anime_list:
        # Adjust based on actual JikanPy response structure for completed list
        anime_info = anime_entry.get('anime', anime_entry) # Adapt if structure differs
        original_title = anime_info.get('title', 'Unknown Title')
        mal_id = anime_info.get('mal_id')

        # Use the MAL ID to ensure we only process each unique anime once,
        if not mal_id or mal_id in titles_processed:
            continue

        sanitized = sanitize_anime_title(original_title)

        if sanitized not in grouped:
            grouped[sanitized] = {'original_titles': set(), 'mal_ids': set(), 'wallpapers': []}

        grouped[sanitized]['original_titles'].add(original_title)
        grouped[sanitized]['mal_ids'].add(mal_id)
        titles_processed.add(mal_id) # Mark this MAL ID as processed

    print(f"Original count: {len(anime_list)}, Grouped count: {len(grouped)}") # Debugging
    return grouped

def fetch_wallpapers(anime_title, count=5):
    """Fetches wallpaper URLs from Wallhaven for a given anime title."""
    if not WALLHAVEN_API_KEY:
        print("Wallhaven API Key not set. Skipping wallpaper fetch.")
        return []

    # Add anime_title to query even if it contains special characters, Wallhaven might handle it
    # Or consider more advanced query crafting e.g., '"' + anime_title + '"' for exact match attempt
    params = {
        'q': anime_title,
        'categories': '010',  # General, Anime, People (0 = General, 1 = Anime, 0 = People)
        'purity': '100',      # SFW only (110=SFW+Sketchy, 111=SFW+Sketchy+NSFW)
        'sorting': 'relevance', # Or 'toplist', 'views', 'random', etc.
        'order': 'desc',
        'apikey': WALLHAVEN_API_KEY
    }
    headers = {'User-Agent': USER_AGENT}
    wallpapers = []
    try:
        print(f"Querying Wallhaven for: {anime_title}")
        response = requests.get(WALLHAVEN_API_URL, params=params, headers=headers, timeout=20) # Increased timeout
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()

        if data and 'data' in data:
            for item in data['data'][:count]: # Get top 'count' results
                 if 'path' in item:
                    wallpapers.append(item['path']) # 'path' is the full image URL

    except requests.exceptions.RequestException as e:
        # Log more specific error if possible (e.g., status code)
        status_code = e.response.status_code if e.response is not None else "N/A"
        print(f"Error fetching wallpapers for '{anime_title}' (Status: {status_code}): {e}")
    except Exception as e:
        print(f"An unexpected error occurred fetching wallpapers for '{anime_title}': {e}")

    print(f"Found {len(wallpapers)} wallpapers for '{anime_title}'") # Debugging
    return wallpapers


# --- API Endpoint ---
@app.route('/api/wallpapers/<username>', methods=['GET'])
def get_user_wallpapers(username):
    if not username:
        return jsonify({"error": "MAL username is required"}), 400

    print(f"Fetching data for MAL user: {username}")

    all_anime_data = []
    page = 1
    # Limit pages to avoid excessively long requests/hitting rate limits.
    # MAL lists can be huge! Consider if you *really* need the whole list
    # or maybe just top N scored/recently completed?
    max_pages = 15 # Increased limit slightly, use with caution

    try:
        while page <= max_pages:
            print(f"Fetching MAL completed list page {page} for {username}...")
            # Fetch user's completed list, ordered by score descending
            user_list_response = jikan.user(username=username, request='animelist', argument='completed', page=page, parameters={'order_by': 'score', 'sort': 'desc'})

            # Jikan V4 structure has data under 'data' key
            current_page_anime = user_list_response.get('data', [])

            if current_page_anime:
                all_anime_data.extend(current_page_anime)
                # Check pagination from Jikan V4 response
                pagination = user_list_response.get('pagination', {})
                if pagination.get('has_next_page', False):
                     page += 1
                     # Rate limit delay for Jikan API (adjust as needed, ~1-2 seconds is polite)
                     time.sleep(2)
                else:
                     print("No more pages found in MAL list.")
                     break # No more pages
            else:
                 # No anime found on this page (or subsequent pages), or error
                 print(f"No anime data found on page {page} or Jikan response format unexpected.")
                 break

        if not all_anime_data:
             # Check if the user exists or list is private (Jikan might raise exception earlier for 404)
             print(f"No completed anime found or profile private/invalid for user: {username}")
             # Attempt a basic user profile fetch to differentiate Not Found vs Empty List
             try:
                 profile = jikan.user(username=username)
                 if profile: # User exists, list must be empty or private
                     return jsonify({"error": f"User '{username}' found, but their completed list is empty or private."}), 404
             except Exception: # Assume user not found if profile fetch fails
                return jsonify({"error": f"MAL user '{username}' not found."}), 404
             # Fallback if profile check complicated things
             return jsonify({"error": f"No completed anime found for user '{username}', or their list is private/empty."}), 404


        print(f"Total completed anime fetched: {len(all_anime_data)}")

        # Group anime
        grouped_anime = group_anime(all_anime_data)

        # Fetch wallpapers for each group
        results = []
        # Add counter for debugging/progress
        group_count = len(grouped_anime)
        current_group = 0
        for base_title, data in grouped_anime.items():
            current_group += 1
            print(f"Processing group {current_group}/{group_count}: Fetching wallpapers for '{base_title}'")
            wallpapers = fetch_wallpapers(base_title, count=5)
            results.append({
                'grouped_title': base_title,
                'original_titles': sorted(list(data['original_titles'])), # Sort for consistent output
                'wallpapers': wallpapers
            })
            # Be polite to Wallhaven API - Rate limit is per minute usually (e.g. 30/min)
            # A short delay helps stay under limits for potentially many groups.
            time.sleep(1.5) # Adjust as needed based on list size and rate limits

        print(f"Finished processing {len(results)} groups.")
        return jsonify(results)

    # More specific error handling based on Jikan exceptions if possible
    except requests.exceptions.HTTPError as e:
         # Handle HTTP errors from Jikan/requests specifically
         status_code = e.response.status_code
         print(f"HTTP error contacting Jikan/MAL for {username}: Status {status_code}, Response: {e.response.text}")
         if status_code == 404:
              return jsonify({"error": f"MAL user '{username}' not found or list is private."}), 404
         elif status_code == 429: # Too Many Requests
              return jsonify({"error": "Rate limit hit fetching MAL data. Please try again later."}), 429
         elif status_code == 403: # Forbidden
              return jsonify({"error": f"Access denied fetching MAL data for '{username}'. List might be private."}), 403
         else:
              return jsonify({"error": f"Could not retrieve MAL data for '{username}'. API returned status {status_code}."}), 503 # Service Unavailable

    except requests.exceptions.RequestException as e:
         # Handle other network errors (DNS, connection refused etc.)
         print(f"Network error contacting Jikan/MAL for {username}: {e}")
         return jsonify({"error": f"Could not connect to MAL services. Check network or try again later."}), 504 # Gateway Timeout

    except Exception as e:
        # Catch potential JikanPy specific errors or other unexpected issues
        print(f"An unexpected error occurred processing MAL user {username}: {e}")
        import traceback
        traceback.print_exc() # Print full traceback to Render logs for debugging
        return jsonify({"error": "An internal server error occurred while processing the request."}), 500

# --- Run the App (for local testing) ---
# This block is NOT used by Render (it uses the Procfile + gunicorn)
# Run `python app.py` in your terminal to test locally
if __name__ == '__main__':
    # Use 0.0.0.0 to be accessible on your local network
    # Default port is 5000
    print("Starting Flask development server...")
    # Turn off debug mode for production simulation, or keep True for local dev details
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)