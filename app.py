# app.py
import os
import re
import requests
import traceback
import json
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
MAL_LIST_URL_TEMPLATE = "https://myanimelist.net/animelist/{username}?status=2"
MAL_JSON_URL_TEMPLATE = "https://myanimelist.net/animelist/{username}/load.json?status=2&offset=0"

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

# --- MAL DATA FETCH FUNCTION (JSON Attempt + HTML Fallback) ---
def fetch_mal_data(username):
    """ Attempts to fetch MAL completed list data, first via undocumented JSON endpoint, then falls back to HTML scraping. """
    anime_data_list = []
    mal_data_fetched_successfully = False
    last_error_message = "Unknown error during MAL fetch."
    processed_ids = set()
    mal_fetch_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"}

    # --- Attempt 1: JSON Endpoint ---
    mal_json_url = MAL_JSON_URL_TEMPLATE.format(username=username)
    print(f"  [MAL Fetch] Attempt 1: Fetching JSON from {mal_json_url}")
    try:
        response = requests.get(mal_json_url, headers=mal_fetch_headers, timeout=20)
        print(f"  [MAL Fetch] JSON attempt - Status Code: {response.status_code}")
        actual_content_type = response.headers.get('Content-Type', 'N/A').lower()
        print(f"  [MAL Fetch] JSON attempt - Content-Type: {actual_content_type}")
        if response.status_code == 200 and 'application/json' in actual_content_type:
            print(f"  [MAL Fetch] JSON attempt - Content-Type OK. Parsing JSON...")
            try:
                mal_data = response.json()
                if isinstance(mal_data, list):
                    print(f"  [MAL Fetch] JSON attempt - Successfully parsed JSON list ({len(mal_data)} items).")
                    count = 0
                    for item in mal_data:
                        if isinstance(item, dict) and item.get('status') == 2:
                            title = item.get('anime_title'); anime_id = item.get('anime_id')
                            if title and anime_id and anime_id not in processed_ids:
                                anime_data_list.append({'title': title.strip(), 'mal_id': anime_id, 'image_url': None })
                                processed_ids.add(anime_id); count += 1
                    print(f"  [MAL Fetch] JSON attempt - Extracted {count} completed titles.")
                    if count > 0: mal_data_fetched_successfully = True
                else: last_error_message = "MAL JSON attempt - Parsed JSON but it was not a list."; print(f"  [MAL Fetch] {last_error_message}")
            except json.JSONDecodeError as e_json: last_error_message = f"MAL JSON attempt - Error decoding JSON: {e_json}"; print(f"  [MAL Fetch] {last_error_message}"); print(f"  [MAL Fetch] Response text snippet: {response.text[:500]}...")
            except Exception as e_loop: last_error_message = f"MAL JSON attempt - Error processing JSON items: {e_loop}"; print(f"  [MAL Fetch] {last_error_message}"); traceback.print_exc()
        else: last_error_message = f"MAL JSON attempt - Failed (Status: {response.status_code}, Content-Type: {actual_content_type})."; print(f"  [MAL Fetch] {last_error_message}")
    except requests.exceptions.RequestException as e: last_error_message = f"MAL JSON attempt - Network Error: {e}"; print(f"  [MAL Fetch] {last_error_message}")
    except Exception as e: last_error_message = f"MAL JSON attempt - Unexpected error: {e}"; print(f"  [MAL Fetch] {last_error_message}"); traceback.print_exc()

    # --- Attempt 2: HTML Scraping Fallback ---
    if not mal_data_fetched_successfully:
        print(f"  [MAL Fetch] Attempt 2: Falling back to HTML scraping...")
        mal_html_url = MAL_LIST_URL_TEMPLATE.format(username=username)
        print(f"  [MAL Fetch] HTML attempt - Requesting URL: {mal_html_url}")
        try:
            response = requests.get(mal_html_url, headers=mal_fetch_headers, timeout=20)
            print(f"  [MAL Fetch] HTML attempt - Status Code: {response.status_code}")
            if response.status_code == 404: raise ValueError(f"MyAnimeList user '{username}' not found or profile is private (HTML check).")
            elif response.status_code != 200: raise ConnectionError(f"Could not fetch MAL HTML page (Status: {response.status_code}).")

            soup = BeautifulSoup(response.text, "html.parser")
            title_tags = soup.select("td.data.title.clearfix a.link.sort")

            if not title_tags:
                 list_table = soup.select_one("table.list-table")
                 if list_table and "No anime found" in list_table.get_text():
                      print(f"  [MAL Fetch] HTML attempt - MAL page indicates 'No anime found'.")
                      mal_data_fetched_successfully = True; anime_data_list = []
                 else: last_error_message = "MAL HTML attempt - No title elements found using selector. MAL structure may have changed."; raise RuntimeError(last_error_message)
            else:
                 count = 0
                 for tag in title_tags:
                     if tag:
                         title = tag.get_text(strip=True); temp_id_placeholder = f"scraped_{title[:20]}"
                         if title and temp_id_placeholder not in processed_ids:
                             anime_data_list.append({'title': title, 'mal_id': None, 'image_url': None })
                             processed_ids.add(temp_id_placeholder); count += 1
                 print(f"  [MAL Fetch] HTML attempt - Extracted {count} titles via scraping.")
                 if count > 0 or (title_tags is not None): mal_data_fetched_successfully = True
        except (ValueError, ConnectionError, RuntimeError) as e: last_error_message = f"MAL HTML attempt - Failed: {e}"; print(f"  [MAL Fetch] {last_error_message}"); if not anime_data_list: raise e
        except requests.exceptions.RequestException as e: last_error_message = f"MAL HTML attempt - Network Error: {e}"; print(f"  [MAL Fetch] {last_error_message}"); if not anime_data_list: raise ConnectionError(last_error_message)
        except Exception as e: last_error_message = f"MAL HTML attempt - Unexpected error: {e}"; print(f"  [MAL Fetch] {last_error_message}"); traceback.print_exc(); if not anime_data_list: raise RuntimeError(last_error_message)

    if not mal_data_fetched_successfully and not anime_data_list:
         print(f"  [MAL Fetch] Both JSON and HTML methods failed to fetch valid data.")
         error_to_raise = ConnectionError(last_error_message) if last_error_message else ConnectionError("Failed to fetch MAL data via all methods.")
         raise error_to_raise

    print(f"  [MAL Fetch] Finished fetch process. Returning {len(anime_data_list)} items.")
    final_list = []; seen_titles = set()
    for item in anime_data_list:
        # Ensure item has a title before adding
        item_title = item.get('title')
        if item_title and item_title not in seen_titles:
            final_list.append(item)
            seen_titles.add(item_title)
    print(f"  [MAL Fetch] Returning {len(final_list)} unique items after deduplication.")
    return final_list

# --- GROUPING FUNCTION (Corrected UnboundLocalError) ---
def group_anime(anime_data_list):
    """ Groups a list of anime data dictionaries by cleaned titles. """
    grouped = {}
    print(f"  [GroupAnime] Starting grouping for {len(anime_data_list)} items.") # Log start
    for item_data in anime_data_list:
        title = item_data.get('title')

        # Check for valid title early in the loop iteration
        if not title:
            print(f"  [GroupAnime] Skipping item with missing title: {item_data}")
            continue # Skip this item entirely if it has no title

        # Only assign other variables if title is valid
        image_url = item_data.get('image_url') # Will likely be None
        display_title = title # Assign display_title here
        search_term = title # Assign search_term here

        grouped_key = clean_anime_title(title)
        if not grouped_key:
            print(f"  [GroupAnime] Skipping item '{title}' because cleaned key is empty.")
            continue # Skip if cleaning results in nothing

        # Now we know display_title, search_term, image_url, and grouped_key are valid (or None for image_url)
        if grouped_key not in grouped:
            grouped[grouped_key] = {
                'display_title': display_title,
                'search_term': search_term,
                'image_url': image_url
            }
        else:
             # Logic to prefer shorter display title for a group
             if len(display_title) < len(grouped[grouped_key]['display_title']):
                  grouped[grouped_key]['display_title'] = display_title
                  # Optionally update search term or image url here if needed,
                  # but current logic keeps the first image_url encountered for simplicity.
                  # grouped[grouped_key]['image_url'] = image_url # Example if you wanted to update
    print(f"  [GroupAnime] Finished grouping. Result has {len(grouped)} groups.") # Log end
    return grouped
# --- END GROUPING FUNCTION CORRECTION ---

# --- WALLHAVEN FUNCTION ---
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

# --- MAIN API ENDPOINT ---
@app.route('/api/wallpapers/<username>')
def get_anime_wallpapers(username):
    """ API endpoint using combined MAL fetch (JSON + HTML fallback). """
    print(f"[Request] Received API request for username: {username}")
    if not username: return jsonify({"error": "MAL username is required"}), 400
    try:
        print(f"  [Flow] Fetching MAL list using combined method for: {username}")
        mal_data_list = fetch_mal_data(username)

        if mal_data_list is not None and not mal_data_list:
             print("  [Result] MAL fetch successful but list is empty.")
             return jsonify({"message": f"No completed anime found for user '{username}'."}), 404
        if mal_data_list is None: # Failsafe
            print("  [Result] MAL fetch failed via all methods.")
            return jsonify({"error": "Failed to fetch MAL data after multiple attempts."}), 503

        print(f"  [Flow] Found {len(mal_data_list)} MAL entries. Grouping...")
        grouped_anime = group_anime(mal_data_list) # Call the corrected group_anime
        print(f"  [Flow] Grouped into {len(grouped_anime)} unique series.")
        if not grouped_anime:
             print("  [Result] No anime could be grouped from fetched data.")
             return jsonify({"message": f"Could not group anime for user '{username}'."}), 500

        results = {}; print(f"  [Flow] Fetching wallpapers (SFW only) from Wallhaven for {len(grouped_anime)} groups...")
        processed_count = 0; total_groups = len(grouped_anime)
        for key, data in grouped_anime.items():
            processed_count += 1
            search_term_for_wallhaven = data['search_term']
            print(f"  [Flow] ({processed_count}/{total_groups}) Processing group: {key} (Searching Wallhaven for: '{search_term_for_wallhaven}')")
            wallpapers = get_wallpapers(search_term_for_wallhaven)
            if wallpapers:
                 results[key] = { 'display_title': data['display_title'], 'mal_cover': data.get('image_url'), 'wallpapers': wallpapers }

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
