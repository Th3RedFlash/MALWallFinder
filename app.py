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
WALLHAVEN_API_URL = "https://wallhaven.cc/api/v1/search"
WALLHAVEN_API_KEY = os.getenv("WALLHAVEN_API_KEY")
WALLPAPER_LIMIT = 5
MAL_LIST_URL_TEMPLATE = "https://myanimelist.net/animelist/{username}?status=2"

# --- Helper Functions ---

def clean_anime_title(title):
    """ Basic cleaning of anime titles for grouping/searching. """
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

def get_mal_completed_list_from_scrape(username):
    """ Fetches and scrapes the completed anime list directly from MAL website. """
    mal_url = MAL_LIST_URL_TEMPLATE.format(username=username)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    print(f"  [Scraper] Requesting URL: {mal_url}")
    try:
        response = requests.get(mal_url, headers=headers, timeout=20)
        print(f"  [Scraper] Response Status Code: {response.status_code}")
        if response.status_code == 404:
            print(f"  [Scraper] Received 404 for user: {username}. MAL profile might be private or non-existent.")
            raise ValueError(f"MyAnimeList user '{username}' not found or profile is private.")
        elif response.status_code != 200:
            print(f"  [Scraper] Received non-200 status code: {response.status_code}")
            raise ConnectionError(f"Could not fetch MAL page (Status: {response.status_code}). Check username and profile visibility.")

        soup = BeautifulSoup(response.text, "html.parser")
        # Ensure this selector matches the current MAL structure
        title_tags = soup.select("td.data.title.clearfix a.link.sort")

        if not title_tags:
            # Check if the list body exists but is empty (MAL structure for zero items)
            list_table = soup.select_one("table.list-table")
            if list_table and "No anime found" in list_table.get_text():
                 print(f"  [Scraper] MAL page indicates 'No anime found'.")
                 return [] # Return empty list for no completed anime
            else:
                 print(f"  [Scraper] No anime title elements found using selector. List might be empty, private, or MAL structure changed.")
                 # It's hard to be sure why it's empty without more checks, return empty for now
                 return []

        anime_titles = [tag.get_text(strip=True) for tag in title_tags if tag]
        print(f"  [Scraper] Found {len(anime_titles)} titles for {username}.")
        return anime_titles
    except requests.exceptions.RequestException as e:
        print(f"  [Scraper] RequestException occurred: {type(e).__name__} - {e}")
        raise ConnectionError(f"Network error fetching MAL page: {e}")
    except Exception as e:
        print(f"  [Scraper] An unexpected error occurred during scraping: {type(e).__name__} - {e}")
        traceback.print_exc()
        raise RuntimeError("Internal error processing MAL page.")

def group_anime(anime_titles_list):
    """ Groups a list of raw anime titles by cleaned titles. """
    grouped = {}
    for title in anime_titles_list:
        if not title: continue
        display_title = title; search_term = title
        grouped_key = clean_anime_title(title)
        if not grouped_key: continue
        if grouped_key not in grouped:
            grouped[grouped_key] = { 'display_title': display_title, 'search_term': search_term }
        else:
             if len(display_title) < len(grouped[grouped_key]['display_title']):
                  grouped[grouped_key]['display_title'] = display_title
    return grouped

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

@app.route('/api/wallpapers/<username>')
def get_anime_wallpapers(username):
    """ API endpoint using direct MAL scraping. """
    print(f"[Request] Received API request for username: {username}")
    if not username: return jsonify({"error": "MAL username is required"}), 400
    try:
        print(f"  [Flow] Fetching MAL list via direct scraping for: {username}")
        mal_title_list = get_mal_completed_list_from_scrape(username)
        if not mal_title_list:
             print("  [Result] Scraper returned no titles. List might be empty or private.")
             return jsonify({"message": f"No completed anime found for user '{username}', list might be empty or private."}), 404

        print(f"  [Flow] Found {len(mal_title_list)} raw titles. Grouping...")
        grouped_anime = group_anime(mal_title_list)
        print(f"  [Flow] Grouped into {len(grouped_anime)} unique series.")
        if not grouped_anime:
             print("  [Result] No anime could be grouped.")
             return jsonify({"message": f"Could not group any anime for user '{username}'."}), 404

        results = {}; print(f"  [Flow] Fetching wallpapers (SFW only) from Wallhaven for {len(grouped_anime)} groups...")
        processed_count = 0; total_groups = len(grouped_anime)
        # --- CORRECTED LOOP ---
        # Iterate through the items (key=grouped_key, data=dict with display/search terms)
        for key, data in grouped_anime.items():
            processed_count += 1
            # Use the 'search_term' from the data dictionary for the Wallhaven search
            # Also use the 'key' (the cleaned title) for logging the group being processed
            search_term_for_wallhaven = data['search_term']
            print(f"  [Flow] ({processed_count}/{total_groups}) Processing group: {key} (Searching Wallhaven for: '{search_term_for_wallhaven}')") # Corrected Log
            wallpapers = get_wallpapers(search_term_for_wallhaven) # Use correct variable
            if wallpapers:
                 # Use 'display_title' from data dict for the result
                 results[key] = { 'display_title': data['display_title'], 'wallpapers': wallpapers }
        # --- END CORRECTED LOOP ---

        print("  [Flow] Finished fetching wallpapers.")
        if not results:
             print("  [Result] No SFW wallpapers found for any grouped anime.")
             return jsonify({"message": "Found completed anime, but no relevant SFW wallpapers could be retrieved from Wallhaven."}), 404

        print(f"  [Result] Returning {len(results)} anime groups with SFW wallpapers.")
        return jsonify(results)

    except ValueError as e: print(f"[Error] ValueError: {e}"); return jsonify({"error": str(e)}), 404
    except ConnectionError as e: print(f"[Error] ConnectionError: {e}"); return jsonify({"error": str(e)}), 503
    except RuntimeError as e: print(f"[Error] RuntimeError: {e}"); return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"[Error] An unhandled error occurred in API endpoint: {type(e).__name__} - {e}")
        traceback.print_exc(); return jsonify({"error": "An unexpected internal server error occurred"}), 500

# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on host 0.0.0.0, port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
