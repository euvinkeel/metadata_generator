import os
import requests
import logging

def read_links(file_path):
    with open(file_path, 'r') as file:
        links = [line.strip() for line in file]
    return links

def fetch_html(url):
    response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    html_text = response.text
    return html_text