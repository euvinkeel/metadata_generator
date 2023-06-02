import configparser

config = configparser.ConfigParser()
config.read('config.ini')
api_key = config.get('API_KEYS', 'openai_key')

def generate_metadata_with_gpt4(html_text, api_key):
    # Call GPT-4 API with the raw HTML content and your API key
    # ...
