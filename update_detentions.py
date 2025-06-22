import requests
from bs4 import BeautifulSoup
import json

# Step 1: fetch
url = "https://tracreports.org/immigration/quickfacts/"
resp = requests.get(url)
soup = BeautifulSoup(resp.text, "html.parser")

# Step 2: Find the detention count by class (robust!)
div = soup.find("div", class_="font-bold text-5xl")
if div:
    count = int(div.text.replace(",", ""))
    print("FOUND:", count)
else:
    raise ValueError("Could not find detention number with class 'font-bold text-5xl'")

# Step 3: write JSON
with open("data/detentions.json", "w") as f:
    json.dump({"total": count}, f)