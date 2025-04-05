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
# Wallhaven API info is not used in this test version's endpoint
# WALLHAVEN_API_URL = "https://wallhaven.cc/api/v1/search"
# WALLHAVEN_API_KEY = os.getenv("WALLHAVEN_API_KEY")
# WALLPAPER_LIMIT = 5
MAL_LIST_URL_TEMPLATE = "https://myanimelist.net/animelist/{username}?status=2" # status=2 is 'Completed'

# --- Helper Functions ---

# NOTE: clean_anime_title and group_anime are not used by the simplified endpoint below,
# but kept here for potential future use / restoration.
def clean_anime_title(title):
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

def group_anime(anime_titles_list):
    grouped = {}; #... (implementation omitted as not used in test endpoint)
    return grouped # Placeholder

# --- MAL SCRAPING FUNCTION (Unchanged from previous version) ---
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
        title_tags = soup.select("td.data.title.clearfix a.link.sort") # Check this selector still works!

        if not title_tags:
            list_table = soup.select_one("table.list-table")
            if list_table and "No anime found" in list_table.get_text():
                 print(f"  [Scraper] MAL page indicates 'No anime found'.")
                 return []
            else:
                 print(f"  [Scraper] No anime title elements found using selector. List might be empty, private, or MAL structure changed.")
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

# --- Routes ---
@app.route('/')
def index():
    """ Serves the main HTML page. """
    print("[Request] Received request for / route")
    try: return render_template('index.html')
    except Exception as e: print(f"[Error] Error rendering template index.html: {type(e).__name__} - {e}"); traceback.print_exc(); raise e

# --- *** SIMPLIFIED API ENDPOINT FOR TESTING *** ---
@app.route('/api/wallpapers/<username>')
def get_anime_wallpapers_test(username):
    """
    TEST VERSION: Fetches MAL list via scraper and returns only the raw title list.
    """
    print(f"[Request] Received TEST API request for username: {username}")
    if not username: return jsonify({"error": "MAL username is required"}), 400
    try:
        print(f"  [Flow-Test] Fetching MAL list via direct scraping for: {username}")
        # Call the scraping function
        mal_title_list = get_mal_completed_list_from_scrape(username)

        if not mal_title_list:
             # Handle empty list return from scraper
             print("  [Result-Test] Scraper returned no titles.")
             # Return 404 with a specific message for this case
             return jsonify({"message": f"No completed anime titles found for user '{username}' by scraper (list empty/private or MAL structure changed?)."}), 404
        else:
             # If titles ARE found, return the list directly
             print(f"  [Result-Test] Returning list of {len(mal_title_list)} raw titles.")
             # Return the list as JSON - the frontend will handle displaying it
             return jsonify(mal_title_list)

    # Handle specific errors raised from scraping function
    except ValueError as e: # User not found / private profile from scraper
        print(f"[Error-Test] ValueError: {e}")
        return jsonify({"error": str(e)}), 404 # Keep 404 for user not found
    except ConnectionError as e: # Network error during scraping
        print(f"[Error-Test] ConnectionError: {e}")
        return jsonify({"error": str(e)}), 503 # Keep 503 for connection issues
    except RuntimeError as e: # Internal processing error (e.g., parsing)
        print(f"[Error-Test] RuntimeError: {e}")
        return jsonify({"error": str(e)}), 500 # Keep 500 for internal errors
    # Generic catch-all for anything else
    except Exception as e:
        print(f"[Error-Test] An unhandled error occurred in API endpoint: {type(e).__name__} - {e}")
        traceback.print_exc(); return jsonify({"error": "An unexpected internal server error occurred"}), 500
# --- *** END OF SIMPLIFIED API ENDPOINT *** ---


# --- Main Execution ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on host 0.0.0.0, port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
