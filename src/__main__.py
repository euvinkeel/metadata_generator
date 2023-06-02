import openai
import configparser
import time
from bs4 import BeautifulSoup, Comment
import asyncio
from random import randint

import nltk
nltk.download('punkt')
from nltk.tokenize import word_tokenize

from csv import DictWriter
from utils import read_links, fetch_html

config = configparser.ConfigParser()
config.read('config.ini')
openai.api_key = config.get('API_KEYS', 'openai_key')
totaltokencount3 = 0
totaltokencount4 = 0

# Adding maximum number of retries and base wait time
MAX_RETRIES = 6
BASE_WAIT_TIME = 5  # seconds


def extract_relevant_text_v3(html_text, min_text_length=50):
    """
    Extracts relevant textual content from raw HTML.

    Parameters:
    - html_text (str): The raw HTML text.
    - min_text_length (int): The minimum length of text to be considered relevant.

    Returns:
    - list: A list of strings, each containing a relevant piece of text.
    """
    soup = BeautifulSoup(html_text, 'html.parser')
    
    content_tags = ['p', 'div', 'span', 'article', 'section']
    relevant_text = []

    navigation_phrases = [
        "Copyright © Innerbody Research",
        "Anatomy Explorer",
        "Change Current View Angle",
        "Toggle Anatomy System",
        "« Back\nShow on Map »\nAnatomy Term",
        "Displayed on other page",
        "POPULAR REVIEWS",
        "GUIDES",
        "BODY SYSTEMS",
        "EXPLORE",
        "Do Not Sell",
        "Policy",
        "Top 10",
        "REVIEWS",
        "Additional Resources",
        "Innerbody Research is the largest home health"
    ]

    for tag in content_tags:
        elements = soup.body.find_all(tag)
        for element in elements:
            text = element.text.strip()
            if (
                len(text) >= min_text_length and 
                text not in navigation_phrases and
                not any(nav_phrase in text for nav_phrase in navigation_phrases)
            ):
                relevant_text.append(text)
    
    return " ".join(relevant_text)


def split_html(html, max_tokens=1000):
    soup = BeautifulSoup(html, 'html.parser')

    # Extract text from HTML
    text = soup.get_text()

    # Tokenize the text
    tokens = word_tokenize(text)
    print("token length:", len(tokens))

    chunks = []
    current_chunk = []

    for token in tokens:
        current_chunk.append(token)

        if len(current_chunk) >= max_tokens:
            chunks.append(' '.join(current_chunk))
            current_chunk = []

    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


async def generate_summary(prompt):
    retries = 0
    while retries < MAX_RETRIES:
        try:
            chat_completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an assistant that generates summaries. Do so concisely and sufficiently. Do not generate anything else."},
                    {"role": "user", "content": prompt},
                    {"role": "user", "content": "Summarize it; only keep core ideas and key informational phrases."},
                ]
            )
            summary = chat_completion.choices[0].message['content']
            print("++SUMMARY GENERATED: ", summary[:120])
            # print("Tokens used:", chat_completion.usage.total_tokens)
            global totaltokencount3
            totaltokencount3 += chat_completion.usage.total_tokens
            time.sleep(1)
            return summary
        except Exception as e:
            # Retry the request after an exponentially increasing delay
            wait_time = BASE_WAIT_TIME * (2 ** retries)
            print(f"Rate limit exceeded. Retrying after {wait_time} seconds...")
            time.sleep(wait_time)
            retries += 1
    # If we've reached the maximum number of retries, raise the last exception
    raise e

# last usd billed: 3.92
# Total 3.5 token count: 253546, approx USD used: 0.507092
# Total 4   token count: 77731, approx USD used: 3.8865499999999997
# About 4.40 USD added?

async def create_completion(messages):
    retries = 0
    while retries < MAX_RETRIES:
        try:
            chat_completion = openai.ChatCompletion.create(
                model="gpt-4",
                messages=messages
            )
            content = chat_completion.choices[0].message['content']
            print("\t", content)
            # print("\t Tokens used:", chat_completion.usage.total_tokens)
            global totaltokencount4
            totaltokencount4 += chat_completion.usage.total_tokens
            return content
        except Exception as e:
            # Retry the request after an exponentially increasing delay
            wait_time = BASE_WAIT_TIME * (2 ** retries)
            print(f"Error: {str(e)}. Retrying after {wait_time} seconds...")
            time.sleep(wait_time)
            retries += 1
    # If we've reached the maximum number of retries, raise the last exception
    raise e

async def process_sections(sections):
    tasks = []
    for section in sections:
        task = generate_summary(section)
        tasks.append(task)
        time.sleep(2)
    section_summaries = await asyncio.gather(*tasks)
    return section_summaries

async def main():
    global totaltokencount4
    file_path = "data/links.txt"

    data = []

    with open('answers.csv', 'w', newline='') as csvfile:
        time.sleep(2)
        fieldnames = ['link', 'h1title', 'metatag', 'len1', 'titletag', 'len2']
        writer = DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        links = read_links(file_path)
        for link in links:
            row = {}
            html_text = fetch_html(link)
            orig_html_text = html_text
            row['link'] = link

            # html_text = strip_non_informational(html_text)
            html_text = extract_relevant_text_v3(html_text, 50)
            print("Stripped from ", len(orig_html_text), "to", len(html_text))
            sections = split_html(html_text, 800)

            # Generate summary for each section
            print("Summarizing...")
            section_summaries = await process_sections(sections)
            print("All summaries complete")

            # Combine section summaries into one summary
            combined_summary = ' '.join(section_summaries)
            print("COMBINED SUMMARY:", len(combined_summary), combined_summary[:120])
            
            final_summary = await generate_summary(combined_summary)
            print("FINAL SUMMARY:", len(final_summary), final_summary[:120])

            # Generate h1 title, metatag, and titletag based on the combined summary
            generatedH1Title = await create_completion([
                {"role": "system", "content": "You are an assistant that generates metadata content for an educational website. You only generate what you've been told, and never anything else. Answer concisely and sufficiently."},
                {"role": "user", "content": f"Write me a short 50-60 character SEO-optimized H1 title about the educational webpage contents. Here's some examples to match the tone of:"},
                {"role": "user", "content": 
                    """Axillary Nodes: Structure, Function, and Location\n
                    Ball-and-Socket Joints: Anatomy and Movement\n"""},
                {"role": "user", "content": final_summary},
            ])

            generatedMetaTag = await create_completion([
                {"role": "system", "content": "You are an assistant that generates metadata for an educational website. You only generate what you've been told, and never anything else. Answer concisely and sufficiently."},
                {"role": "user", "content": "Write me a roughly 130-170 character, SEO-optimized metatag about the educational webpage contents. Don't say ANYTHING about medical advice; only educational value."},
                {"role": "user", "content": final_summary},
            ])

            generatedTitleTag = await create_completion([
                {"role": "system", "content": "You are an assistant that generates title tags for an educational website. You only generate what you've been told, and never anything else. Answer concisely and sufficiently."},
                {"role": "user", "content": "Write me a short 45-60 character, SEO-optimized title tag about the educational webpage contents. Here's some examples to match the tone of:"},
                {"role": "user", "content": 
                    """Axillary Nodes: Structure, Function & Location\n
                    Ball-and-Socket Joints: Anatomy & Movement\n"""},
                {"role": "user", "content": final_summary},
            ])

            # fieldnames = ['link', 'h1title', 'metatag', 'len1', 'titletag', 'len2']
            row['h1title'] = generatedH1Title
            row['metatag'] = generatedMetaTag
            row['len1'] = len(generatedMetaTag)
            row['titletag'] = generatedTitleTag
            row['len2'] = len(generatedTitleTag)

            # print("COMPLETE ROW OUTPUT:")
            # print(row)
            data.append(row)
            writer.writerow(row)
            print(f"Total 3.5 token count: {totaltokencount3}, approx USD used: {totaltokencount3 / 1000 * 0.002}")
            print(f"Total 4   token count: {totaltokencount4}, approx USD used: {totaltokencount4 / 1000 * 0.05}")
            print("\n\n\n")

if __name__ == "__main__":
    asyncio.run(main())
