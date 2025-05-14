import requests
from bs4 import BeautifulSoup
import time
import json

HEADERS = {"User-Agent": "Mozilla/5.0"}
BASE_URL = "https://www.yelp.com"
SEARCH_URL = f"{BASE_URL}/search"

def get_page_soup(page_number):
    params = {
        "find_desc": "Matcha",
        "find_loc": "London",
        "start": page_number * 10  # 10 results per page
    }
    response = requests.get(SEARCH_URL, headers=HEADERS, params=params)
    if response.status_code != 200:
        print(f"Failed to fetch page {page_number}")
        return None
    return BeautifulSoup(response.text, "html.parser")

def parse_business_cards(soup):
    businesses = []
    cards = soup.select('li[class*="container"] > div[class*="businessName"]')  # Selector is intentionally generic
    for card in cards:
        try:
            name_tag = card.find('a')
            name = name_tag.text
            link = BASE_URL + name_tag['href']

            parent = card.find_parent('li')
            rating_tag = parent.select_one('div[aria-label*="star rating"]')
            rating = float(rating_tag['aria-label'].split(' ')[0]) if rating_tag else None

            review_tag = parent.select_one('span[class*="reviewCount"]')
            review_count = int(review_tag.text.strip()) if review_tag else 0

            address_tag = parent.select_one('address')
            address = address_tag.text.strip() if address_tag else "N/A"

            businesses.append({
                "name": name,
                "link": link,
                "rating": rating,
                "reviews": review_count,
                "address": address
            })
        except Exception as e:
            print("Error parsing a card:", e)
    return businesses

def scrape_yelp(pages=3):
    all_results = []
    for page in range(pages):
        print(f"Scraping page {page + 1}")
        soup = get_page_soup(page)
        if not soup:
            break
        businesses = parse_business_cards(soup)
        all_results.extend(businesses)
        time.sleep(2)  # Delay to avoid rate-limiting

    # Rank by rating and then by number of reviews
    all_results.sort(key=lambda b: (-b["rating"], -b["reviews"]))
    with open("matcha_london_ranked.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Saved {len(all_results)} entries to matcha_london_ranked.json")

if __name__ == "__main__":
    scrape_yelp(pages=5)  # Scrape first 5 pages
