import re
from collections import Counter
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import hashlib

# Keep original constants at module level
EXCLUDED_EXTENSIONS = [
    '.css', '.js', '.bmp', '.gif', '.jpe', '.jpeg', '.jpg', '.ico', '.png', '.tif', '.tiff', '.pdf',
    '.mp3', '.mp4', '.avi', '.mov', '.mpeg', '.tar', '.gz', '.zip', '.rar', '.swf', '.flv', '.wma',
    '.wmv', '.mid', '.bam', '.ppt'
]

STOP_WORDS = [ "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves", "zero", "able", "across", "among", "anyhow", "anyone", "anything", "anyway", "anywhere", "beside", "besides", "between", "beyond", "con", "considering", "could", "de", "due", "except", "excepting", "followed", "following", "gone", "instead", "inside", "neither", "next", "nobody", "none", "nor", "outside", "perhaps", "regarding", "since", "someone", "something", "sometime", "sometimes", "somewhere", "throughout", "toward", "towards", "unless", "unlike", "upon", "whenever", "wherever", "whichever", "whilst", "without", "yes", "yet" ]

class ContentStats:
    def __init__(self):
        self.visited_urls = set()
        self.longest_page_url = ""
        self.longest_page_word_count = 0
        self.common_words = Counter()
        self.subdomain_pages = {}
        self.visited_patterns = {}
        self.visited_hashes = set()

    def update_longest_page(self, url, word_count):
        if word_count > self.longest_page_word_count:
            self.longest_page_word_count = word_count
            self.longest_page_url = url

    def save_stats(self):
        self._save_longest_page()
        self._save_unique_pages()
        self._save_common_words()
        self._save_subdomains()

    def _save_longest_page(self):
        with open('longest_page.txt', 'w') as file:
            file.write(f"Longest Page: {self.longest_page_url} with {self.longest_page_word_count} words\n")

    def _save_unique_pages(self):
        with open('unique_pages.txt', 'w') as file:
            file.write(f"Total Unique Pages: {len(self.visited_urls)}\n")

    def _save_common_words(self):
        with open('common_words.txt', 'w') as file:
            file.write("Most Common Words:\n")
            for word, count in self.common_words.most_common(50):
                file.write(f"{word}: {count}\n")

    def _save_subdomains(self):
        with open('subdomains.txt', 'w') as file:
            sorted_subdomains = sorted((k, v) for k, v in self.subdomain_pages.items() if k is not None)
            for subdomain, urls in sorted_subdomains:
                example_url = next(iter(urls))
                parsed = urlparse(example_url)
                formatted_subdomain = f"{parsed.scheme}://{parsed.netloc}"
                file.write(f"{formatted_subdomain}, {len(urls)}\n")

def is_valid(url):
    """
    Checks whether a given URL is valid for further processing.
    """
    try:
        # Parse the URL and remove any fragment
        parsed_url = urlparse(url)
        sanitized_url = parsed_url._replace(fragment="").geturl()
        
        # Check for a valid scheme
        if parsed_url.scheme not in {"http", "https"}:
            return False
        
        # Ensure the URL matches specific domains
        valid_domains_pattern = r".*\.(ics|cs|informatics|stat)\.uci\.edu.*"
        if not re.match(valid_domains_pattern, parsed_url.netloc):
            return False
        
        # Check if the path ends with any excluded extension
        if any(sanitized_url.lower().endswith(ext) for ext in EXCLUDED_EXTENSIONS):
            return False
        
        # URL passed all checks
        return True
    except TypeError as e:
        print(f"Error processing URL: {url} - {e}")
        raise

def extract_next_links(url, resp):
    """
    Extracts links from the content of a given URL.
    """
    # Return an empty list if the response is not valid
    if resp.status != 200 or not resp.raw_response:
        return []
    
    # Parse the page content using BeautifulSoup
    soup = BeautifulSoup(resp.raw_response.content, 'html.parser')
    
    # Generate a set of unique, valid absolute links
    links = {
        urlparse(urljoin(resp.raw_response.url, anchor['href']))._replace(fragment="").geturl()
        for anchor in soup.find_all('a', href=True)
        if is_valid(urlparse(urljoin(resp.raw_response.url, anchor['href']))._replace(fragment="").geturl())
    }
    
    # Convert the set to a list for consistent output
    return list(links)

def process_content(url, content, stats):
    """Process page content and update statistics."""
    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text()
    words = re.findall(r'\b\w+\b', text.lower())
    filtered_words = [word for word in words if word not in STOP_WORDS and len(word) > 2]
    
    # Update statistics
    word_count = len(words)
    stats.update_longest_page(url, word_count)
    stats.common_words.update(filtered_words)
    
    # Update subdomain statistics
    parsed = urlparse(url)
    if parsed.netloc.endswith('ics.uci.edu'):
        if parsed.netloc not in stats.subdomain_pages:
            stats.subdomain_pages[parsed.netloc] = set()
        stats.subdomain_pages[parsed.netloc].add(url)

def detect_trap(url, stats):
    """Detect potential URL traps."""
    pattern = re.sub(r'\d+', '[digit]', urlparse(url).path)
    stats.visited_patterns[pattern] = stats.visited_patterns.get(pattern, 0) + 1
    return stats.visited_patterns[pattern] > 10

def detect_similar_content(url, content, stats):
    """Detect similar content using content hashing."""
    soup = BeautifulSoup(content, 'html.parser')
    text = soup.get_text()
    normalized_text = re.sub(r'\s+', ' ', text).strip().lower()
    content_hash = hashlib.md5(normalized_text.encode('utf-8')).hexdigest()
    
    if content_hash in stats.visited_hashes:
        print(f"Similar content detected for URL {url}, skipping...")
        return True
    stats.visited_hashes.add(content_hash)
    return False

def handle_redirects(resp):
    """Handle HTTP redirects."""
    if 300 <= resp.status < 400:
        redirected_url = resp.headers.get('Location', '')
        if redirected_url:
            return urljoin(resp.url, redirected_url)
    return resp.url

def is_dead_url(resp):
    """Check if URL is dead (returns 200 but no content)."""
    if resp.status == 200:
        if resp.raw_response:
            return len(resp.raw_response.content) == 0
        return True
    return False

def has_high_information_content(resp):
    """Check if page contains sufficient content."""
    if not resp.raw_response:
        return False
    soup = BeautifulSoup(resp.raw_response.content, 'html.parser')
    text = soup.get_text()
    words = re.findall(r'\b\w+\b', text.lower())
    return len(words) >= 100

def scraper(url, resp):
    # Initialize stats object if not exists
    if not hasattr(scraper, 'stats'):
        scraper.stats = ContentStats()
    
    # Skip if already visited
    if url in scraper.stats.visited_urls:
        return []
    
    # Check for traps and invalid content
    if detect_trap(url, scraper.stats) or is_dead_url(resp) or not has_high_information_content(resp):
        print(f"No information or trap detected for URL {url}, skipping...")
        return []
    
    final_url = handle_redirects(resp)
    scraper.stats.visited_urls.add(final_url)

    if detect_similar_content(final_url, resp.raw_response.content, scraper.stats):
        return []
    
    if resp.status == 200 and resp.raw_response and resp.raw_response.content:
        process_content(final_url, resp.raw_response.content, scraper.stats)
        scraper.stats.save_stats()

    links = extract_next_links(final_url, resp)
    return [link for link in links if is_valid(link)]