import googlemaps
import json
from datetime import datetime
import time
import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import logging
import traceback

# Set up logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler('matcha_detection.log'),
        logging.StreamHandler()
    ]
)

def validate_places_api(client):
    """Test if the Places API is properly enabled and accessible"""
    try:
        # Try a simple places nearby search
        test_result = client.places_nearby(
            location={'lat': 51.5074, 'lng': -0.1278},  # London coordinates
            radius=1000,
            type='cafe'
        )
        if 'results' in test_result:
            logging.info("Places API test successful")
            return True
        return False
    except Exception as e:
        logging.error(f"Places API test failed: {str(e)}")
        if "REQUEST_DENIED" in str(e):
            logging.error("""
Places API is not enabled or not authorized. Please:
1. Go to https://console.cloud.google.com/
2. Select your project
3. Go to 'APIs & Services' > 'Library'
4. Search for 'Places API'
5. Click 'Enable'
6. Wait a few minutes for the changes to take effect
""")
        return False

def get_api_key():
    try:
        # First try to get from environment variable
        api_key = os.getenv('GOOGLE_PLACES_API_KEY')
        
        if not api_key:
            logging.info("No API key found in environment variables")
            # If not in environment, ask user
            api_key = input("Please enter your Google Places API key: ").strip()
            
            if not api_key:
                raise ValueError("API key is required to run this script")
        
        logging.debug(f"API key length: {len(api_key)}")
        return api_key
    except Exception as e:
        logging.error(f"Error getting API key: {str(e)}")
        logging.error(traceback.format_exc())
        raise

def initialize_google_maps():
    try:
        api_key = get_api_key()
        logging.info("Initializing Google Maps client...")
        client = googlemaps.Client(key=api_key)
        
        # Test the Places API specifically
        logging.info("Testing Places API access...")
        if not validate_places_api(client):
            raise Exception("Places API test failed. Please check the logs for details.")
            
        return client
    except Exception as e:
        logging.error(f"Error initializing Google Maps client: {str(e)}")
        logging.error(traceback.format_exc())
        print("\nTo get an API key:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a new project or select an existing one")
        print("3. Enable the Places API")
        print("4. Go to Credentials and create an API key")
        exit(1)

def check_menu_for_matcha(website_url):
    """Check the website's menu for matcha items"""
    if not website_url:
        logging.info("No website URL provided")
        return False
    
    try:
        logging.info(f"Checking menu at: {website_url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        response = requests.get(website_url, headers=headers, timeout=10)
        if response.status_code != 200:
            logging.warning(f"Failed to fetch website: {response.status_code}")
            return False
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Common menu-related keywords and their variations
        menu_keywords = [
            'menu', 'drinks', 'beverages', 'coffee', 'tea',
            'cafe', 'café', 'coffee shop', 'coffeeshop',
            'drink menu', 'beverage menu', 'coffee menu',
            'tea menu', 'hot drinks', 'cold drinks'
        ]
        
        # Look for menu sections in various HTML elements
        menu_text = ""
        menu_sections_found = []
        
        # Check for menu links first
        menu_links = []
        for keyword in menu_keywords:
            links = soup.find_all('a', href=True, string=re.compile(keyword, re.I))
            menu_links.extend(links)
        
        if menu_links:
            logging.info(f"Found {len(menu_links)} potential menu links")
            for link in menu_links:
                menu_url = link['href']
                if not menu_url.startswith(('http://', 'https://')):
                    # Handle relative URLs
                    base_url = f"{urlparse(website_url).scheme}://{urlparse(website_url).netloc}"
                    menu_url = base_url + ('' if menu_url.startswith('/') else '/') + menu_url
                
                try:
                    menu_response = requests.get(menu_url, headers=headers, timeout=10)
                    if menu_response.status_code == 200:
                        menu_soup = BeautifulSoup(menu_response.text, 'html.parser')
                        menu_text += menu_soup.get_text() + " "
                except Exception as e:
                    logging.warning(f"Failed to fetch menu page {menu_url}: {e}")
        
        # Look for menu sections in the main page
        for keyword in menu_keywords:
            # Check in various HTML elements
            elements = soup.find_all(['div', 'section', 'article', 'nav', 'ul', 'ol', 'table'], 
                                   string=re.compile(keyword, re.I))
            for element in elements:
                section_text = element.get_text().strip()
                if section_text:
                    menu_sections_found.append(f"Found '{keyword}' section: {section_text[:100]}...")
                    menu_text += section_text + " "
        
        logging.info(f"Menu sections found: {len(menu_sections_found)}")
        for section in menu_sections_found:
            logging.info(section)
        
        # Matcha-related keywords and variations
        matcha_patterns = [
            r'matcha\s*(?:latte|tea|drink|coffee|frappuccino|smoothie|shake)',
            r'matcha\s*(?:green\s*tea|powder)',
            r'(?:iced|hot)\s*matcha',
            r'matcha\s*(?:with|and)\s*(?:milk|soy|almond|oat)',
            r'ceremonial\s*matcha',
            r'matcha\s*(?:espresso|shot)',
            r'matcha\s*(?:cake|cookie|brownie|muffin|pastry)',
            r'matcha\s*(?:ice\s*cream|gelato)',
            r'matcha\s*(?:pancake|waffle)',
            r'matcha\s*(?:doughnut|donut)'
        ]
        
        # Check for matcha patterns in menu text
        for pattern in matcha_patterns:
            matches = re.finditer(pattern, menu_text, re.I)
            for match in matches:
                logging.info(f"Found matcha pattern '{pattern}': {match.group()}")
                return True
                
        logging.info("No matcha items found in menu")
        return False
        
    except Exception as e:
        logging.error(f"Error checking menu: {e}")
        return False

def check_for_matcha(place_details):
    """Comprehensive check for matcha availability"""
    has_matcha = False
    matcha_evidence = []
    place_name = place_details.get('name', 'Unknown')
    
    logging.info(f"\nChecking for matcha at: {place_name}")
    
    # 1. Check reviews
    if 'reviews' in place_details:
        logging.info(f"Checking {len(place_details['reviews'])} reviews")
        for i, review in enumerate(place_details['reviews'], 1):
            review_text = review.get('text', '').lower()
            if 'matcha' in review_text:
                has_matcha = True
                matcha_evidence.append("Found in reviews")
                logging.info(f"Matcha found in review {i}: {review_text[:100]}...")
                break
    else:
        logging.info("No reviews available")
    
    # 2. Check website/menu
    website = place_details.get('website')
    if website:
        logging.info(f"Checking website: {website}")
        if check_menu_for_matcha(website):
            has_matcha = True
            matcha_evidence.append("Found on menu")
    else:
        logging.info("No website available")
    
    # 3. Check name and description
    name = place_details.get('name', '').lower()
    if 'matcha' in name:
        has_matcha = True
        matcha_evidence.append("Found in name")
        logging.info(f"Matcha found in name: {name}")
    
    # 4. Check editorial summary
    if 'editorial_summary' in place_details:
        summary = place_details['editorial_summary'].get('overview', '').lower()
        if 'matcha' in summary:
            has_matcha = True
            matcha_evidence.append("Found in editorial summary")
            logging.info(f"Matcha found in editorial summary: {summary[:100]}...")
    
    # 5. Check types/categories
    types = place_details.get('types', [])
    logging.info(f"Business types: {types}")
    if 'cafe' in types or 'coffee_shop' in types:
        matcha_evidence.append("Is a cafe/coffee shop")
    
    logging.info(f"Final result for {place_name}: {'Has matcha' if has_matcha else 'No matcha'} - Evidence: {matcha_evidence}")
    return has_matcha, matcha_evidence

def search_coffee_shops(gmaps, location="London, UK", radius=5000):
    coffee_shops = []
    next_page_token = None
    page_count = 0
    detailed_searches_attempted = 0 # Counter for attempted detail fetches

    try:
        # Geocode location string to coordinates
        geocode_result = gmaps.geocode(location)
        if not geocode_result:
            logging.error(f"Could not geocode location: {location}")
            # Fallback to default coordinates if geocoding fails
            lat_lng = {'lat': 51.5074, 'lng': -0.1278} # Default London coordinates
            logging.warning(f"Using default London coordinates: {lat_lng}")
        else:
            lat_lng = geocode_result[0]['geometry']['location']
    except Exception as e:
        logging.error(f"Error geocoding location: {str(e)}")
        if "REQUEST_DENIED" in str(e) and "This API project is not authorized to use this API" in str(e):
            logging.error("Geocoding API is not enabled or authorized for this project.")
            logging.error("Please enable the 'Geocoding API' in your Google Cloud Console for this project.")
        # Fallback to default coordinates if geocoding fails
        lat_lng = {'lat': 51.5074, 'lng': -0.1278} # Default London coordinates
        logging.warning(f"Using default London coordinates due to error: {lat_lng}")

    logging.info(f"Starting search for coffee shops in {lat_lng}...")
    logging.debug(f"Search parameters: location={lat_lng}, radius={radius}")

    while True:
        page_count += 1
        logging.info(f"Fetching page {page_count}{f' (token: {next_page_token[:10]}...)' if next_page_token else ''}...")
        try:
            response = gmaps.places_nearby(
                location=lat_lng,
                radius=radius,
                type='cafe', # Assuming we are looking for cafes primarily
                page_token=next_page_token
            )
        except googlemaps.exceptions.ApiError as e:
            logging.error(f"Google Maps API error on page {page_count}: {e}")
            if "INVALID_REQUEST" in str(e) and next_page_token:
                 logging.error("Received INVALID_REQUEST with a page token. This can happen if the token is too old. Stopping pagination.")
                 break # Stop if page token becomes invalid
            # Consider other specific error handling (e.g., OVER_QUERY_LIMIT)
            break # Exit loop on API error
        except Exception as e:
            logging.error(f"Unexpected error during places_nearby call on page {page_count}: {e}")
            break

        logging.debug(f"API Response: {json.dumps(response, indent=2)}")

        results = response.get('results', [])
        logging.info(f"Received {len(results)} results on page {page_count}")

        for place_summary in results:
            place_id = place_summary.get('place_id')
            if not place_id:
                logging.warning(f"Skipping a place due to missing place_id: {place_summary.get('name', 'Unknown name')}")
                continue

            detailed_searches_attempted += 1
            logging.info(f"Fetching details for place: {place_summary.get('name', 'Unknown name')} (ID: {place_id}) (Attempt {detailed_searches_attempted})")
            try:
                # Fetch detailed information including website
                place_details_data = gmaps.place(
                    place_id=place_id,
                    fields=['name', 'website', 'reviews', 'editorial_summary', 'type', 'place_id', 'formatted_address', 'geometry', 'opening_hours', 'photo', 'rating', 'user_ratings_total', 'price_level', 'business_status']
                ).get('result')
                
                if not place_details_data:
                    logging.warning(f"No details returned for place_id: {place_id}")
                    continue

                # The check_for_matcha function expects the full place details
                has_matcha, matcha_evidence = check_for_matcha(place_details_data)
                
                shop_info = {
                    'name': place_details_data.get('name'),
                    'address': place_details_data.get('formatted_address'),
                    'place_id': place_id,
                    'website': place_details_data.get('website'), # Ensure website is included
                    'has_matcha': has_matcha,
                    'matcha_evidence': matcha_evidence,
                    'details': place_details_data # Storing all details for potential future use
                }
                coffee_shops.append(shop_info)
                logging.info(f"Processed: {shop_info['name']} - Matcha: {has_matcha} (Evidence: {matcha_evidence})")

            except googlemaps.exceptions.ApiError as e:
                logging.error(f"Google Maps API error fetching details for {place_id}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error fetching details for {place_id}: {e}")
                logging.error(traceback.format_exc())
        
        next_page_token = response.get('next_page_token')
        if not next_page_token:
            logging.info("No more pages to fetch.")
            break
        
        logging.info("Waiting before fetching next page...")
        time.sleep(2) # Wait for 2 seconds before fetching the next page token to avoid overwhelming the API and ensure token is valid

    logging.info(f"Attempted to fetch details for a total of {detailed_searches_attempted} places.")
    logging.info(f"Found {len(coffee_shops)} coffee shops matching criteria.")
    return coffee_shops

def main():
    try:
        logging.info("Starting the matcha cafe finder...")
        gmaps = initialize_google_maps()
        logging.info("\nSearching for coffee shops with matcha in London...")
        
        coffee_shops = search_coffee_shops(gmaps)
        
        if not coffee_shops:
            logging.info("\nNo coffee shops serving matcha were found.")
            return
        
        # Sort by rating and number of reviews
        coffee_shops.sort(key=lambda x: (-x['details'].get('rating', 0), -x['details'].get('user_ratings_total', 0)))
        
        # Save results to file
        output_file = 'london_matcha_cafes.json'
        with open(output_file, 'w') as f:
            json.dump(coffee_shops, f, indent=2)
        
        logging.info(f"\nFound {len(coffee_shops)} coffee shops serving matcha in London")
        logging.info(f"Results have been saved to {output_file}")
        
        # Print top 5 results
        logging.info("\nTop 5 Matcha Cafes in London:")
        for i, shop in enumerate(coffee_shops[:5], 1):
            logging.info(f"\n{i}. {shop['name']}")
            rating = shop['details'].get('rating', 'N/A')
            user_ratings_total = shop['details'].get('user_ratings_total', 'N/A')
            logging.info(f"   Rating: {rating} ({user_ratings_total} reviews)")
            logging.info(f"   Address: {shop['address']}")
            logging.info(f"   Matcha Evidence: {', '.join(shop['matcha_evidence'])}")
            if shop.get('website'):
                logging.info(f"   Website: {shop['website']}")
            
    except Exception as e:
        logging.error(f"An error occurred in main: {str(e)}")
        logging.error(traceback.format_exc())
        logging.error(f"Full error details: {json.dumps(e.__dict__, indent=2)}")

if __name__ == "__main__":
    main()