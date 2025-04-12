import requests
import argparse
import concurrent.futures
import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
from typing import List, Tuple, Set
import time

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()

# Move constants outside class for better memory usage
DEBUG_PATTERNS = {pattern.lower() for pattern in [
    "DisallowedHost at",
    "phpdebugbar",
    "Whoops! There was an error",
    "X-Debug-Token:",
    "Symfony Web Debug Toolbar",
    "Struts Problem Report",
    "DebugKit",
    "Traceback (most recent call last):",
    "django.template",
    "TemplateSyntaxError",
    "ValueError:",
    "KeyError:",
    "TypeError:",
    "werkzeug.exceptions",
    "jinja2.exceptions",
    "Internal Server Error",
    "Exception Location:",
    "Request Method:",
    "Request URL:",
    "Python version:",
    "Laravel Debugbar",
    "Symfony\\Component\\",
    "Parse error:",
    "Fatal error:",
    "stack trace:",
    "in /var/www/",
    "java.lang.NullPointerException",
    "at org.springframework",
    "ExceptionReport",
    "ActionController::RoutingError",
    "ActiveRecord::",
    "Rails.root:",
    "rack.session"
]}

KNOWN_DEBUG_PATHS = [
    "symfony/profiler",
    "_debugbar",
    "wp-json/wp/v2/debug",
    "debug/default/view",
    "__debug__",
    "_profiler",
    "phpinfo.php"
]

METHODS = ["GET", "POST", "PUT"]
MALFORMED_JSON = ['{\"kk\":\"\";', '{\"incomplete\":true']

class DebugDetector:
    def __init__(self, max_workers: int = 20, timeout: int = 5):
        self.max_workers = max_workers
        self.timeout = timeout
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/json,*/*',
            'Connection': 'keep-alive'
        }

    async def init_session(self):
        """Initialize aiohttp session with connection pooling"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            connector = aiohttp.TCPConnector(limit=self.max_workers, ssl=False)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.headers
            )

    def check_debug_patterns(self, response_text: str) -> str:
        """Check for debug patterns in response text using set operations"""
        response_lower = response_text.lower()
        for pattern in DEBUG_PATTERNS:
            if pattern in response_lower:
                return pattern
        return None

    async def make_request(self, url: str, method: str = 'GET', data: dict = None) -> Tuple[int, str]:
        """Make an HTTP request with error handling"""
        try:
            async with getattr(self.session, method.lower())(url, data=data) as response:
                if response.status == 404:
                    return 404, ""
                text = await response.text()
                return response.status, text
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return 0, ""

    async def check_url(self, url: str) -> Tuple[str, List[Tuple[str, str]]]:
        """Check a single URL for debug mode"""
        results = []
        
        # Basic GET request
        status, text = await self.make_request(url)
        if status == 404:
            return url, []
        
        if match := self.check_debug_patterns(text):
            results.append(("Simple GET", match))

        # Check different HTTP methods
        for method in METHODS:
            status, text = await self.make_request(url, method=method)
            if status == 404:
                continue
            if match := self.check_debug_patterns(text):
                results.append((f"HTTP Method {method}", match))

        # Check debug paths
        debug_tasks = []
        for path in KNOWN_DEBUG_PATHS:
            debug_url = urljoin(url + "/", path)
            debug_tasks.append(self.make_request(debug_url))
        
        debug_responses = await asyncio.gather(*debug_tasks)
        for path, (status, text) in zip(KNOWN_DEBUG_PATHS, debug_responses):
            if status == 404:
                continue
            if match := self.check_debug_patterns(text):
                results.append((f"Debug path: {path}", match))

        return url, results

    async def scan_urls(self, urls: List[str]):
        """Scan multiple URLs concurrently"""
        await self.init_session()
        tasks = [self.check_url(url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        if self.session:
            await self.session.close()
        
        return results

def print_banner():
    logo = r'''
  ,--.,--.      ,--.  ,--.          ,--.   
 ,-|  ||  |-.  ,-|  |,-'  '-. ,---.,-'  '-. 
' .-. || .-. '' .-. |'-.  .-'| .--''-.  .-' 
\ `-' || `-' |\ `-' |  |  |  \ `--.  |  |   
 `---'  `---'  `---'   `--'   `---'  `--'   
            dbdtct — Web Debug Mode Detection Tool
            Created by: Youssef Lahouifi
            Supervised by: Redouane Korchiyne
'''
    print(logo)

async def main():
    print_banner()
    parser = argparse.ArgumentParser(description="Detect exposed debug interfaces on web applications.")
    parser.add_argument('-u', '--url', help='Target URL')
    parser.add_argument('-l', '--list', help='File containing list of URLs')
    parser.add_argument('-w', '--workers', type=int, default=20, help='Number of concurrent workers')
    args = parser.parse_args()

    urls = []
    if args.url:
        urls.append(args.url.strip())
    if args.list:
        with open(args.list, 'r') as f:
            urls.extend(line.strip() for line in f if line.strip())

    if not urls:
        parser.error("No URLs provided. Use -u or -l option.")

    start_time = time.time()
    detector = DebugDetector(max_workers=args.workers)
    results = await detector.scan_urls(urls)

    # Print results
    for url, findings in results:
        if findings:
            print(f"\n[+] Potential Debug Mode Detected on {url}")
            for method, match in findings:
                print(f"    -> Technique: {method}")
                print(f"    -> Fingerprint: {match}")
        else:
            print(f"[-] No debug patterns found on {url}")

    print(f"\nScan completed in {time.time() - start_time:.2f} seconds")

if __name__ == '__main__':
    asyncio.run(main())
