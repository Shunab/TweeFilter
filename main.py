import time
import json
import openai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
from keyword_mapping import keyword_to_token


with open('config.json') as f:
  data = json.load(f)

creds_file = data['google_sheets']['credentials_file']
all_tweets_sheet_name = data['google_sheets']['raw_tweets_sheet']
filtered_tweets_sheet_name = data['google_sheets']['filtered_tweets_sheet']
discord_webhook_urls = data['discord']['webhook_urls']
last_row_file = data['last_row_file']

#Get usermap from config.json
with open('config.json') as f:
  data = json.load(f)

user_map = data['user_map']

# Google Sheets setup
scope = [
  'https://spreadsheets.google.com/feeds',
  'https://www.googleapis.com/auth/drive'
]
creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
client = gspread.authorize(creds)

# Get the sheets
all_tweets_sheet = client.open(all_tweets_sheet_name).sheet1
filtered_tweets_sheet = client.open(filtered_tweets_sheet_name).sheet1

# OpenAI setup
prompt = "This is a tweet: \"{}\". Is this related to cryptocurrency, financial markets, shitcoins, news related to rate hikes, contains stock tags like $, respond with yes even if unsure or if think the tweet has a picture that I might find relevant"


def remove_mentions(content):
  words = content.split()
  while words and words[0].startswith("@"):
    words.pop(0)
  return " ".join(words)


def contains_keyword(content):
  with open('keywords.txt', 'r') as file:
    keywords = file.read().splitlines()
  return any(keyword in content for keyword in keywords)


def read_last_row(filename):
  with open(filename, 'r') as file:
    return int(file.read().strip())


def update_last_row(filename, row_number):
  with open(filename, 'w') as file:
    file.write(str(row_number))


def is_relevant(tweet):
  content = remove_mentions(tweet)

  if contains_keyword(content):
    # Token/security check
    token_prompt = "This is a tweet: \"{}\". What token or security is being referred to? If unsure, respond with 'undefined'."
    response = openai.Completion.create(engine="text-davinci-003",
                                        prompt=token_prompt.format(content),
                                        temperature=0.5,
                                        max_tokens=3)
    token = response.choices[0].text.strip()

    # Sentiment check
    sentiment_prompt = "This is a tweet: \"{}\". What is the sentiment towards the token or security? If unsure, respond with 'undefined'."
    response = openai.Completion.create(engine="text-davinci-003",
                                        prompt=sentiment_prompt.format(content),
                                        temperature=0.5,
                                        max_tokens=3)
    sentiment = response.choices[0].text.strip()

    return True, token, sentiment

  openai_api_keys = data['openai']['api_keys']
  for key in openai_api_keys:
    try:
      openai.api_key = key

      # Relevance check
      relevance_prompt = "This is a tweet: \"{}\". Is this related to cryptocurrency, financial markets, shitcoins, news related to rate hikes, contains stock tags like $, respond with yes even if unsure or if think the tweet has a picture that I might find relevant"
      response = openai.Completion.create(engine="text-davinci-003",
                                          prompt=relevance_prompt.format(content),
                                          temperature=0.5,
                                          max_tokens=3)
      relevance = response.choices[0].text.strip().lower() == 'yes'

      if not relevance:
        return False, None, None

      # Token/security check
      token_prompt = "This is a tweet: \"{}\". What token or security is being referred to? If unsure, respond with 'undefined'."
      response = openai.Completion.create(engine="text-davinci-003",
                                          prompt=token_prompt.format(content),
                                          temperature=0.5,
                                          max_tokens=3)
      token = response.choices[0].text.strip()

      # Sentiment check
      sentiment_prompt = "This is a tweet: \"{}\". What is the sentiment towards the token or security? If unsure, respond with 'undefined'."
      response = openai.Completion.create(engine="text-davinci-003",
                                          prompt=sentiment_prompt.format(content),
                                          temperature=0.5,
                                          max_tokens=3)
      sentiment = response.choices[0].text.strip()

      return relevance, token, sentiment

    except openai.error.APIError as e:
      print(f"APIError with key {key}: {e}")
      continue  # Switch to the next key

  raise Exception("All OpenAI API keys exhausted")

def send_to_discord(row):
  username = row[1].lstrip("@")
  author_info = user_map.get(username, {
    "name": "Unknown",
    "icon_url": "https://unavatar.io/twitter"
  })
  tweet_content = row[2]
  tweet_url = row[3]
  token = row[4]
  sentiment = row[5]

  for url in discord_webhook_urls:
    payload = {
      "username": "Twitter",
      "avatar_url": "https://unavatar.io/twitter",
      "content": "",
      "tts": False,
      "embeds": [
        {
          "title": "Link to Tweet",
          "description": tweet_content,
          "url": tweet_url,
          "color": 1940464,
          "author": {
            "name": author_info['name'],
            "url": tweet_url,
            "icon_url": author_info['icon_url']
          },
          "fields": [
            {
              "name": "Coin",
              "value": token,
              "inline": True
            },
            {
              "name": "Sentiment",
              "value": sentiment,
              "inline": True
            }
          ]
        }
      ]
    }

    headers = {'Content-Type': 'application/json'}
    requests.post(url, data=json.dumps(payload), headers=headers)


last_checked_row = read_last_row(last_row_file)

while True:
  rows = all_tweets_sheet.get_all_values()
  for i in range(last_checked_row, len(rows)):
    row = rows[i]
    print(f"Checking row {i+1}")
    tweet = row[2]
    relevance, token, sentiment = is_relevant(tweet)
    if relevance:
      row.extend([token, sentiment])  
      filtered_tweets_sheet.append_row(row)
      send_to_discord(row)  
      print("Tweet is relevant")
    else:
      print("Tweet is not relevant")

  last_checked_row = len(rows)
  update_last_row(last_row_file, last_checked_row)

  time.sleep(60)

