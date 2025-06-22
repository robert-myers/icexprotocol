import requests
from bs4 import BeautifulSoup
import json
import re

# Step 1: fetch
url = "https://tracreports.org/immigration/quickfacts/"
resp = requests.get(url)
soup = BeautifulSoup(resp.text, "html.parser")

# Step 2: Find the detention count and date (robust!)
div = soup.find("div", class_="font-bold text-5xl")
date_elem = soup.find("div", class_="font-base text-lg")
if div and date_elem:
    count = int(div.text.replace(",", ""))
    # Try to extract the date from the text, e.g., "in detention on June 15, 2025"
    m = re.search(r"in detention on (.+)", date_elem.text)
    if m:
        date = m.group(1).strip()
    else:
        date = ""
    print("FOUND:", count, date)
else:
    raise ValueError("Could not find detention number or date in expected classes.")

# Step 3: write JSON
with open("data/detentions.json", "w") as f:
    json.dump({"total": count, "date": date}, f)