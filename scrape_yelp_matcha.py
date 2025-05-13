import requests
from html.parser import HTMLParser
import json

class YelpMatchaParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_name = False
        self.names = []

    def handle_starttag(self, tag, attrs):
        for attr in attrs:
            if tag == 'a' and 'class' in dict(attrs) and 'css-19v1rkv' in dict(attrs)['class']:
                self.in_name = True

    def handle_endtag(self, tag):
        if tag == 'a':
            self.in_name = False

    def handle_data(self, data):
        if self.in_name:
            self.names.append(data)

def scrape_yelp():
    url = "https://www.yelp.com/search?find_desc=Matcha&find_loc=London"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    parser = YelpMatchaParser()
    parser.feed(response.text)

    data = [{"name": name} for name in parser.names]
    with open("matcha_london.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(data)} entries to matcha_london.json")

if __name__ == "__main__":
    scrape_yelp()
