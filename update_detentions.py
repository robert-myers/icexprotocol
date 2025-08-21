import requests
from bs4 import BeautifulSoup
import json
import re

url = "https://tracreports.org/immigration/quickfacts/"
resp = requests.get(url)
soup = BeautifulSoup(resp.text, "html.parser")

output = {}

# 1. Total in ICE detention (first "font-bold text-5xl" number)
all_bold_numbers = soup.find_all("div", class_="font-bold text-5xl")
if all_bold_numbers and len(all_bold_numbers) > 0:
    output["detention_total"] = int(all_bold_numbers[0].text.replace(",", "").strip())
else:
    output["detention_total"] = None

# 2. Total in ICE detention date ("in detention on ...")
dates = soup.find_all(string=lambda t: "in detention on" in t or "in ICE detention according to" in t)
detention_date = None
for d in dates:
    nxt = d.find_next(string=True)
    if nxt and "," in nxt:
        detention_date = nxt.strip().replace(".", "")
        break
output["detention_total_date"] = detention_date


# 3. No criminal conviction stats
nocrim_number = None
nocrim_date = None
conviction_text_node = soup.find(string=lambda t: "no criminal conviction" in t.lower())
if conviction_text_node:
    # Work within the surrounding grid card for this fact
    container = conviction_text_node.find_parent("div", class_="grid")
    if container:
        # Find the first numeric <strong> inside this card (that is NOT a percent)
        for strong in container.find_all("strong"):
            txt = strong.text.strip().replace(",", "")
            if txt.isdigit():
                nocrim_number = int(txt)
                break
        # Find a <strong> that looks like a date (e.g. June 15, 2025)
        for strong in container.find_all("strong"):
            if re.search(r"[A-Za-z]+\s+\d{1,2},\s+\d{4}", strong.text):
                nocrim_date = strong.text.strip()
                break

output["no_criminal_conviction"] = nocrim_number
output["no_criminal_conviction_date"] = nocrim_date


# 4. ATD monitored stats
atd_number = None
atd_date = None
atd_text_node = soup.find(string=lambda t: "alternatives to detention" in t.lower() and "monitoring" in t.lower())
if atd_text_node:
    container = atd_text_node.find_parent("div", class_="grid")
    if container:
        # Find a big bold number in this card
        for bold in container.find_all("div", class_="font-bold text-5xl"):
            num_txt = bold.text.replace(",", "").strip()
            if num_txt.isdigit():
                atd_number = int(num_txt)
                break
        # Pull the first date-looking string in the container
        date_match = re.search(r"[A-Za-z]+\s+\d{1,2},\s+\d{4}", container.get_text())
        if date_match:
            atd_date = date_match.group(0)

output["atd_monitored"] = atd_number
output["atd_monitored_date"] = atd_date

with open("data/detentions.json", "w") as f:
    json.dump(output, f, indent=2)

print(json.dumps(output, indent=2))