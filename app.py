# app.py
import os
import re
import requests
import traceback
from bs4 import BeautifulSoup # Import BeautifulSoup
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# --- Configuration ---
# No longer using Jikan URL
WALLHAVEN_API_URL = "https://wallhaven.cc/api/v1/search"
WALLHAVEN_API_KEY = os.getenv("WALLHAVEN_API_KEY")
WALLPAPER_LIMIT = 5
MAL_LIST_URL_TEMPLATE = "https://myanimelist.net/animelist/{username}?status=2" # status=2 is 'Completed'

# --- Helper Functions ---

def clean_anime_title(title):
    """ Basic cleaning of anime titles for grouping/searching. """
    # This function remains largely the same, but might need tuning
    # based on how titles appear directly from MAL HTML vs Jikan.
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

# --- NEW MAL SCRAPING FUNCTION (based on user file) ---
def get_mal_completed_list_from_scrape(username):
    """
    Fetches and scrapes the completed anime list directly from MAL website.
    Returns a list of anime titles.
    Raises Exceptions on failure.
    """
    mal_url = MAL_LIST_URL_TEMPLATE.format(username=username)
    # Use a realistic User-Agent header
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    print(f"  [Scraper] Requesting URL: {mal_url}")

    try:
        response = requests.get(mal_url, headers=headers, timeout=20)
        print(f"  [Scraper] Response Status Code: {response.status_code}")

        # Check for non-200 status explicitly
        if response.status_code == 404:
            print(f"  [Scraper] Received 404 for user: {username}. MAL profile might be private or non-existent.")
            # Use ValueError consistent with previous Jikan error handling
            raise ValueError(f"MyAnimeList user '{username}' not found or profile is private.")
        elif response.status_code != 200:
            print(f"  [Scraper] Received non-200 status code: {response.status_code}")
            # Use ConnectionError for other connection/server issues
            raise ConnectionError(f"Could not fetch MAL page (Status: {response.status_code}). Check username and profile visibility.")

        # Proceed with parsing if status is 200
        soup = BeautifulSoup(response.text, "html.parser")
        # Selector from user's file: 'td.data.title.clearfix a.link.sort'
        # This selector might need updating if MAL changes its HTML structure!
        title_tags = soup.select("td.data.title.clearfix a.link.sort")

        if not title_tags:
            # Check if the list is potentially hidden or empty - MAL page structure might differ
            # Looking for signs of a private list or just empty list can be complex
            print(f"  [Scraper] No anime title elements found using selector. List might be empty, private, or MAL structure changed.")
            # Return empty list, let the main endpoint handle this
            return []

        anime_titles = [tag.get_text(strip=True) for tag in title_tags if tag]
        print(f"  [Scraper] Found {len(anime_titles)} titles for {username}.")
        return anime_titles

    except requests.exceptions.RequestException as e:
        print(f"  [Scraper] RequestException occurred: {type(e).__name__} - {e}")
        raise ConnectionError(f"Network error fetching MAL page: {e}")
    except Exception as e:
        # Catch other potential errors (like parsing errors)
        print(f"  [Scraper] An unexpected error occurred during scraping: {type(e).__name__} - {e}")
        traceback.print_exc()
        raise RuntimeError("Internal error processing MAL page.")

# --- MODIFIED GROUPING FUNCTION (Works with list of titles) ---
def group_anime(anime_titles_list):
    """
    Groups a list of raw anime titles by cleaned titles.
    Returns a dictionary: { 'grouped_key': {'display_title': title, 'search_term': title} }
    """
    grouped = {}
    for title in anime_titles_list:
        if not title: continue
        # Use the original title for display and search initially
        display_title = title
        search_term = title
        # Generate a simpler key for grouping similar seasons/parts
        grouped_key = clean_anime_title(title)
        if not grouped_key: continue

        if grouped_key not in grouped:
            # Store the first encountered title as the display/search term for the group
            grouped[grouped_key] = {
                'display_title': display_title,
                'search_term': search_term
                # NOTE: No 'mal_cover' available from this scraping method
            }
        else:
             # Optional: Logic to prefer shorter titles as display title for the group
             if len(display_title) < len(grouped[grouped_key]['display_title']):
                  grouped[grouped_key]['display_title'] = display_title
                  # Decide if search term should also update (maybe prefer shorter?)
                  # grouped[grouped_key]['search_term'] = display_title
    return grouped

# --- WALLHAVEN FUNCTION (Unchanged) ---
def get_wallpapers(anime_title):
    """ Fetches SFW wallpapers for an anime title from Wallhaven. """
    params = { 'q': anime_title, 'categories': '010', 'purity': '100', 'sorting': 'relevance' }
    headers = {}; print(f"    [Wallhaven] Searching for (SFW only): {anime_title}")
    if WALLHAVEN_API_KEY: headers['X-API-Key'] = WALLHAVEN_API_KEY
    try:
        response = requests.get(WALLHAVEN_API_URL, params=params, headers=headers, timeout=15)
        print(f"    [Wallhaven] Response Status Code: {response.status_code}")
        response.raise_for_status()
        wallpapers_data = response.json().get('data', [])
        results = []
        for wall in wallpapers_data[:WALLPAPER_LIMIT]:
            thumb = wall.get('thumbs', {}).get('large'); full_img = wall.get('path')
            if thumb and full_img: results.append({'thumbnail': thumb, 'full': full_img})
        print(f"    [Wallhaven] Found {len(results)} SFW wallpapers.")
        return results
    except requests.exceptions.RequestException as e:
        print(f"    [Wallhaven] RequestException occurred: {type(e).__name__} - {e}")
        status_code = getattr(e.response, 'status_code', 'N/A')
        if status_code == 429: print("    [Wallhaven] Received 429 Too Many Requests.")
        return []
    except Exception as e:
        print(f"    [Wallhaven] An unexpected error occurred fetching Wallhaven data: {type(e).__name__} - {e}")
        return []

# --- Routes ---
@app.route('/')
def index():
    """ Serves the main HTML page. """
    print("[Request] Received request for / route")
    try: return render_template('index.html')
    except Exception as e: print(f"[Error] Error rendering template index.html: {type(e).__name__} - {e}"); traceback.print_exc(); raise e

# --- MODIFIED API ENDPOINT ---
@app.route('/api/wallpapers/<username>')
def get_anime_wallpapers(username):
    """ API endpoint using direct MAL scraping. """
    print(f"[Request] Received API request for username: {username}")
    if not username: return jsonify({"error": "MAL username is required"}), 400
    try:
        print(f"  [Flow] Fetching MAL list via direct scraping for: {username}")
        # Call the NEW scraping function
        mal_title_list = get_mal_completed_list_from_scrape(username)

        if not mal_title_list:
             # Handle empty list return from scraper
             print("  [Result] Scraper returned no titles. List might be empty or private.")
             return jsonify({"message": f"No completed anime found for user '{username}', list might be empty or private."}), 404

        print(f"  [Flow] Found {len(mal_title_list)} raw titles. Grouping...")
        # Call the MODIFIED grouping function
        grouped_anime = group_anime(mal_title_list)
        print(f"  [Flow] Grouped into {len(grouped_anime)} unique series.")
        if not grouped_anime:
             print("  [Result] No anime could be grouped.")
             return jsonify({"message": f"Could not group any anime for user '{username}'."}), 404 # Should be rare if titles were found

        results = {}; print(f"  [Flow] Fetching wallpapers (SFW only) from Wallhaven for {len(grouped_anime)} groups...")
        processed_count = 0; total_groups = len(grouped_anime)
        for key, data in grouped_anime.items():
            processed_count += 1; print(f"  [Flow] ({processed_count}/{total_groups}) Processing group: {key}")
            wallpapers = get_wallpapers(data['search_term'])
            if wallpapers:
                 # NOTE: No 'mal_cover' included in the result anymore
                 results[key] = { 'display_title': data['display_title'], 'wallpapers': wallpapers }

        print("  [Flow] Finished fetching wallpapers.")
        if not results:
             print("  [Result] No SFW wallpapers found for any grouped anime.")
             return jsonify({"message": "Found completed anime, but no relevant SFW wallpapers could be retrieved from Wallhaven."}), 404

        print(f"  [Result] Returning {len(results)} anime groups with SFW wallpapers.")
        return jsonify(results)

    # Handle specific errors raised from scraping/helper functions
    except ValueError as e: # User not found / private profile from scraper
        print(f"[Error] ValueError: {e}")
        return jsonify({"error": str(e)}), 404
    except ConnectionError as e: # Network error during scraping
        print(f"[Error] ConnectionError: {e}")
        return jsonify({"error": str(e)}), 503
    except RuntimeError as e: # Internal processing error (e.g., parsing)
        print(f"[Error] RuntimeError: {e}")
        return jsonify({"error": str(e)}), 500
    # Generic catch-all for anything else
    except Exception as e:
        print(f"[Error] An unhandled error occurred in API endpoint: {type(e).__name__} - {e}")
        traceback.print_exc(); return jsonify({"error": "An unexpected internal server error occurred"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on host 0.0.0.0, port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
