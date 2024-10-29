import re
from collections import Counter
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import hashlib

EXCLUDED_EXTENSIONS = [
    '.css', '.js', '.bmp', '.gif', '.jpe', '.jpeg', '.jpg', '.ico', '.png', '.tif', '.tiff', '.pdf',
    '.mp3', '.mp4', '.avi', '.mov', '.mpeg', '.tar', '.gz', '.zip', '.rar', '.swf', '.flv', '.wma',
    '.wmv', '.mid', '.bam', '.ppt'
]

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", 
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", 
    "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", 
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have", 
    "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", 
    "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", 
    "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", 
    "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", 
    "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", 
    "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", 
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", 
    "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", 
    "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", 
    "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", 
    "your", "yours", "yourself", "yourselves"
}

visited_urls = set()
longest_page_url = ''
longest_page_word_count = 0
common_words_counter = Counter()
subdomain_pages = {}
visited_patterns = {}
visited_hashes = set()


def scraper(url, resp):
    global visited_urls
    # Skip already visited URLs
    if url in visited_urls:
        return []
    
    if detect_trap(url) or is_dead_url(resp) or not has_high_information_content(resp):
        print(f"No information or trap detected for URL {url}, skipping...")
        return []
    
    final_url = handle_redirects(resp)
    visited_urls.add(final_url)

    if detect_similar_content(final_url, resp.raw_response.content):
        return []
    
    
    if resp.status == 200 and resp.raw_response and resp.raw_response.content:
        word_count = count_words(resp.raw_response.content)
        record_longest_page(final_url, word_count)
        process_subdomain(final_url)
        find_most_common_words(resp.raw_response.content)


    # Save the information about the longest page and subdomains
    save_unique_pages()
    save_most_common_words()
    save_longest_page()
    save_subdomain_info()

    links = extract_next_links(final_url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    """
    Extracts links from the content of a given URL.

    Args:
        url (str): The URL of the page from which links are to be extracted.
        resp (Response): The response object containing the URL content.

    Returns:
        list: List of valid absolute URLs extracted from the page content.
    """
    if resp.status != 200 or not resp.raw_response:
        return[]
    
    # Parse the content to extract links
    soup = BeautifulSoup(resp.raw_response.content, 'html.parser')
    links = []
    for link in soup.find_all('a', href = True):
        # Resolve relative links into absolute URLs
        absolute_link = urljoin(resp.raw_response.url, link['href'])
        absolute_link = urlparse(absolute_link)._replace(fragment="").geturl()
        if is_valid(absolute_link): 
            links.append(absolute_link)
    return links

def is_valid(url):
    """
    Checks whether a given URL is valid for further processing.

    Args:
        url (str): The URL to be validated.

    Returns:
        bool: True if the URL is valid, False otherwise.
    """
    try:
        parsed = urlparse(url)
        url = parsed._replace(fragment="").geturl()
        if parsed.scheme not in set(["http", "https"]):
            return False
        if not re.match(
            r".*\.(ics|cs|informatics|stat)\.uci\.edu.*", parsed.netloc):
            return False
        if any(parsed.path.lower().endswith(ext) for ext in EXCLUDED_EXTENSIONS):
            return False  
        # Remove URL fragments
        url = parsed._replace(fragment="").geturl()
        return True
    except TypeError:
        print("TypeError for URL:", url)
        raise

def count_words(html_content):
    """
    Counts the number of words in the HTML content.

    Args:
        html_content (bytes): The HTML content of a page.

    Returns:
        int: The count of words in the content.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    words = re.findall(r'\b\w+\b', text.lower())
    return len(words)

def record_longest_page(url, word_count):
    """
    Records the information about the longest page encountered.

    Args:
        url (str): The URL of the page.
        word_count (int): The count of words in the page content.
    """
    global longest_page_url, longest_page_word_count
    if word_count > longest_page_word_count:
        longest_page_word_count = word_count
        longest_page_url = url
    
def extract_subdomain(url):
    parsed = urlparse(url)
    if parsed.netloc.endswith('ics.uci.edu'):
        return parsed.netloc
    return None

def process_subdomain(url):
    subdomain = extract_subdomain(url)
    if subdomain not in subdomain_pages:
        subdomain_pages[subdomain] = set()
    subdomain_pages[subdomain].add(url)


def save_longest_page():
    with open('longest_page.txt', 'w') as file:
        file.write(f"Longest Page: {longest_page_url} with {longest_page_word_count} words\n")

def save_subdomain_info():
    with open('subdomains.txt', 'w') as file:
        for subdomain, urls in sorted(subdomain_pages.items()):
            example_url = next(iter(urls))
            parsed_url = urlparse(example_url)
            scheme = parsed_url.scheme
            netloc = parsed_url.netloc

            formatted_subdomain = f"{scheme}://{netloc}"
            file.write(f"{formatted_subdomain}, {len(urls)}\n")


def normalize_url(url):
    """
    Normalizes a URL by excluding fragments and query parameters.

    Args:
        url (str): The URL to be normalized.

    Returns:
        str: The normalized URL.
    """
    parsed = urlparse(url)
    # Normalize to exclude URL fragments and query parameters
    normalized = parsed._replace(query="", fragment="").geturl()
    return normalized

def get_url_pattern(url):
    """
    Extracts a URL pattern by replacing digits with a placeholder.

    Args:
        url (str): The URL from which the pattern is to be extracted.

    Returns:
        str: The URL pattern.
    """
    parsed = urlparse(url)
    path = parsed.path
    return re.sub(r'\d+', '[digit]', path)


def detect_trap(url):
    pattern = get_url_pattern(normalize_url(url))
    if pattern in visited_patterns:
        visited_patterns[pattern] += 1
    else:
        visited_patterns[pattern] = 1

    # Detect a trap if a pattern is visited too frequently
    if visited_patterns[pattern] > 10:
        return True
    return False


def find_most_common_words(html_content):
    """
    Updates the global common_words_counter with words from the HTML content.

    Args:
        html_content (bytes): The HTML content of a page.
    """
    word_counts = count_words_in_content(html_content)
    common_words_counter.update(word_counts)

def count_words_in_content(html_content):
    """
    Counts the words in HTML content, filtering out stop words.

    Args:
        html_content (bytes): The HTML content of a page.

    Returns:
        Counter: A Counter object containing word counts.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    words = re.findall(r'\b\w+\b', text.lower())
    filtered_words = [word for word in words if word not in STOP_WORDS and len(word) > 2]
    return Counter(filtered_words)

def save_most_common_words():
    with open('common_words.txt', 'w') as file:
        file.write("Most Common Words:\n")
        for word, count in common_words_counter.most_common(50):
            file.write(f"{word}: {count}\n")


def is_dead_url(resp):
    """
    Checks if the URL is a dead URL (returns a 200 status but no data).

    Args:
        resp (Response): The response object containing the URL content.

    Returns:
        bool: True if the URL is a dead URL, False otherwise.
    """
    # Check if the response status is 200
    if resp.status == 200:
        # Check if the response contains content
        if resp.raw_response:
            # Check if the content length is zero
            if len(resp.raw_response.content) == 0:
                return True  # Dead URL
        else:
            return True  # Dead URL
    return False  # Not a dead URL

def has_high_information_content(resp):
    """
    Checks if the page contains significant textual information.

    Args:
        resp (Response): The response object containing the URL content.

    Returns:
        bool: True if the page contains significant textual information, False otherwise.
    """
    # Ensure that the response contains content
    if not resp.raw_response:
        return False

    # Extract text content from the HTML
    soup = BeautifulSoup(resp.raw_response.content, 'html.parser')
    text = soup.get_text()

    # Count the number of words
    words = re.findall(r'\b\w+\b', text.lower())
    word_count = len(words)

    if word_count < 100:
        return False
    else:
        return True
    

def handle_redirects(resp):
    """
    Handles HTTP redirects by returning the final URL after all redirects.

    Args:
        resp (Response): The response object from the HTTP request.

    Returns:
        str: The final URL after following all redirects.
    """
    if 300 <= resp.status < 400:
        redirected_url = resp.headers.get('Location', '')
        if redirected_url:
            return urljoin(resp.url, redirected_url)
    return resp.url

def get_content_hash(html_content):
    """
    Generates a hash for the textual content of a web page.

    Args:
        html_content (bytes): The HTML content of a page.

    Returns:
        str: A hash of the text content.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    # Normalize whitespace and lower the case for uniformity
    normalized_text = re.sub(r'\s+', ' ', text).strip().lower()
    return hashlib.md5(normalized_text.encode('utf-8')).hexdigest()

def detect_similar_content(url, html_content):
    """
    Detects if the given page content is similar to any previously encountered page.

    Args:
        url (str): The URL of the page being checked.
        html_content (bytes): The HTML content of the page.

    Returns:
        bool: True if similar content is detected, otherwise False.
    """
    content_hash = get_content_hash(html_content)
    if content_hash in visited_hashes:
        print(f"Similar content detected for URL {url}, skipping...")
        return True
    else:
        visited_hashes.add(content_hash)
        return False


def save_unique_pages():
    with open('unique_pages.txt', 'w') as file:
        file.write(f"Total Unique Pages: {len(visited_urls)}\n")


## OLD CODE


# import re
# from urllib.parse import urlparse

# def scraper(url, resp):
#     links = extract_next_links(url, resp)
#     return [link for link in links if is_valid(link)]

# def extract_next_links(url, resp):
#     # Implementation required.
#     # url: the URL that was used to get the page
#     # resp.url: the actual url of the page
#     # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
#     # resp.error: when status is not 200, you can check the error here, if needed.
#     # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
#     #         resp.raw_response.url: the url, again
#     #         resp.raw_response.content: the content of the page!
#     # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
#     return list()

# def is_valid(url):
#     # Decide whether to crawl this url or not. 
#     # If you decide to crawl it, return True; otherwise return False.
#     # There are already some conditions that return False.
#     try:
#         parsed = urlparse(url)
#         if parsed.scheme not in set(["http", "https"]):
#             return False
#         return not re.match(
#             r".*\.(css|js|bmp|gif|jpe?g|ico"
#             + r"|png|tiff?|mid|mp2|mp3|mp4"
#             + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
#             + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
#             + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
#             + r"|epub|dll|cnf|tgz|sha1"
#             + r"|thmx|mso|arff|rtf|jar|csv"
#             + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

#     except TypeError:
#         print ("TypeError for ", parsed)
#         raise
