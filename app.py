# app.py
import os
import re
import requests
import traceback
import json # Import json library
from bs4 import BeautifulSoup
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
# MAL URLs
MAL_LIST_URL_TEMPLATE = "https://myanimelist.net/animelist/{username}?status=2" # HTML page
MAL_JSON_URL_TEMPLATE = "https://myanimelist.net/animelist/{username}/load.json?status=2&offset=0" # Undocumented JSON endpoint

# --- Helper Functions ---

def clean_anime_title(title):
    """ Basic cleaning of anime titles for grouping/searching. """
    # Using the simpler cleaning function for now
    text = title.lower()
    text = re.sub(r'\s(season\s?\d+|s\d+)\b', '', text)
    text = re.sub(r'\s(part\s?\d+|p\d+)\b', '', text)
    text = re.sub(r'\s(cour\s?\d+)\b', '', text)
    text = re.sub(r'\s?:\s?(the movie|movie|ova|ona|special|tv special)\b', '', text)
    text = re.sub(r'\s\(\d{4}\)<span class="math-inline">', '', text\)
text \= re\.sub\(r'\\s\\\(tv\\\)</span>', '', text)
    text = re.sub(r'\s(2nd season|3rd season|4th season|5th season)', '', text)
    text = re.sub(r'\s[ivx]+<span class="math-inline">', '', text\)
text \= text\.replace\('\:', ' '\)\.replace\('\-', ' '\)
text \= ' '\.join\(text\.split\(\)\)
return text\.strip\(\)
\# Definition for simplify\_title from the FastAPI code \(optional to use later\)
\# def simplify\_title\(title\)\:
\#     title \= title\.strip\(\); match\_colon \= re\.search\(r'\:\\s', title\)
\#     if match\_colon\: title \= title\[\:match\_colon\.start\(\)\]\.strip\(\)
\#     cleaned\_title \= re\.split\(r'\\s\+\\b\(?\:Season\|Part\|Cour\|Movies?\|Specials?\|OVAs?\|Partie\|Saison\|Staffel\|The Movie\|Movie\|Film\|\\d\{1,2\}\)\\b', title, maxsplit\=1, flags\=re\.IGNORECASE\)\[0\]
\#     cleaned\_title \= re\.sub\(r'\\s\*\[\:\\\-\]\\s\*</span>', '', cleaned_title).strip()
#     if re.match(r'.+\s+\d+<span class="math-inline">', cleaned\_title\)\: cleaned\_title \= re\.split\(r'\\s\+\\d\+</span>', cleaned_title)[0].strip()
#     return cleaned_title if cleaned_title else title


# --- NEW MAL DATA FETCH FUNCTION (JSON Attempt + HTML Fallback) ---
def fetch_mal_data(username):
    """
    Attempts to fetch MAL completed list data, first via undocumented JSON endpoint,
    then falls back to HTML scraping.
    Returns a list of dictionaries: [{'title': str, 'mal_id': int|None, 'image_url': str|None}]
    Raises exceptions on complete failure.
    """
    anime_data_list = []
    mal_data_fetched_successfully = False
    last_error_message = "Unknown error during MAL fetch."
    processed_ids = set() # To avoid duplicates if both methods run weirdly

    # Define headers once
    # Using a common browser User-Agent can sometimes help avoid simple blocks
    mal_fetch_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"}

    # --- Attempt 1: JSON Endpoint ---
    mal_json_url = MAL_JSON_URL_TEMPLATE.format(username=username)
    print(f"  [MAL Fetch] Attempt 1: Fetching JSON from {mal_json_url}")
    try:
        response = requests.get(mal_json_url, headers=mal_fetch_headers, timeout=20)
        print(f"  [MAL Fetch] JSON attempt - Status Code: {response.status_code}")
        actual_content_type = response.headers.get('Content-Type', 'N/A').lower()
        print(f"  [MAL Fetch] JSON attempt - Content-Type: {actual_content_type}")

        # Check if response looks like valid JSON and status is OK
        if response.status_code == 200 and 'application/json' in actual_content_type:
            print(f"  [MAL Fetch] JSON attempt - Content-Type OK. Parsing JSON...")
            try:
                mal_data = response.json()
                # Check if it's the expected list format
                if isinstance(mal_data, list):
                    print(f"  [MAL Fetch] JSON attempt - Successfully parsed JSON list ({len(mal_data)} items).")
                    count = 0
                    for item in mal_data:
                        # status=2 means completed in MAL's list data
                        if isinstance(item, dict) and item.get('status') == 2:
                            title = item.get('anime_title')
                            anime_id = item.get('anime_id')
                            # MAL JSON often doesn't include a direct image URL easily here
                            # We could potentially construct one, but let's keep it simple
                            image_url = None # item.get('anime_image_path') # Usually not present/useful directly
                            if title and anime_id and anime_id not in processed_ids:
                                anime_data_list.append({
                                    'title': title.strip(),
                                    'mal_id': anime_id,
                                    'image_url': image_url # Will be None
                                })
                                processed_ids.add(anime_id)
                                count += 1
                    print(f"  [MAL Fetch] JSON attempt - Extracted {count} completed titles.")
                    if count > 0:
                        mal_data_fetched_successfully = True
                else:
                    last_error_message = "MAL JSON attempt - Parsed JSON but it was not a list."
