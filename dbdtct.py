import requests
import argparse
import concurrent.futures
import asyncio
import aiohttp
from urllib.parse import urljoin, urlparse
import time
import socket
from datetime import datetime

# Disable SSL warnings
requests.packages.urllib3.disable_warnings()


DEBUG_PATTERNS = [
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
]

KNOWN_DEBUG_PATHS = [
    "symfony/profiler",
    "_debugbar",
    "wp-json/wp/v2/debug",
    "debug/default/view",
    "__debug__",
    "_profiler",
    "phpinfo.php",
    "debug/",
    "console/",
    "admin/console",
    "api/debug",
    "dev.php",
    "dev",
    "test.php",
    "test",
    "tests/",
    ".env",
    "config.php",
    "config.yml",
    "configuration.php"
]

METHODS = ["GET", "POST", "PUT"]
MALFORMED_JSON = [
'{"foo":"bar"'
]

class DebugDetector:
    def __init__(self, max_workers=20, timeout=5):
        self.max_workers = max_workers
        self.timeout = timeout
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/json,*/*',
            'Connection': 'keep-alive'
        }

    async def init_session(self):
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            connector = aiohttp.TCPConnector(limit=self.max_workers, ssl=False)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self.headers
            )

    def check_debug_patterns(self, response_text):
        response_lower = response_text.lower()
        for pattern in DEBUG_PATTERNS:
            if pattern.lower() in response_lower:
                return pattern
        return None

    async def make_request(self, url, method='GET', data=None):
        try:
            headers = self.headers.copy()
            if data and isinstance(data, str) and data.startswith('{'):
                headers['Content-Type'] = 'application/json'
                
            async with getattr(self.session, method.lower())(
                url, 
                data=data,
                headers=headers,
                ssl=False
            ) as response:
                if response.status == 404:
                    return 404, ""
                text = await response.text()
                return response.status, text
        except:
            return 0, ""

    async def check_url(self, url):
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
            match = self.check_debug_patterns(text)
            if match:
                results.append((f"HTTP Method {method}", match))

        # Test malformed JSON payloads
        for malformed in MALFORMED_JSON:
            try:
                status, text = await self.make_request(
                    url, 
                    method='POST', 
                    data=malformed
                )
                if status != 404:
                    match = self.check_debug_patterns(text)
                    if match:
                        results.append((f"Malformed JSON ({malformed})", match))
            except:
                continue

        # Try accessing by IP
        try:
            parsed = urlparse(url)
            ip = socket.gethostbyname(parsed.hostname)
            ip_url = url.replace(parsed.hostname, ip)
            
            status, text = await self.make_request(ip_url)
            if status != 404:
                match = self.check_debug_patterns(text)
                if match:
                    results.append(("IP-based access", match))
        except:
            pass

        # Check debug paths
        debug_tasks = []
        for path in KNOWN_DEBUG_PATHS:
            debug_url = urljoin(url + "/", path)
            debug_tasks.append(self.make_request(debug_url))
        
        debug_responses = await asyncio.gather(*debug_tasks)
        for path, (status, text) in zip(KNOWN_DEBUG_PATHS, debug_responses):
            if status == 404:
                continue
            match = self.check_debug_patterns(text)
            if match:
                results.append((f"Debug path: {path}", match))

        return url, results

    async def scan_urls(self, urls):
        await self.init_session()
        tasks = [self.check_url(url) for url in urls]
        results = await asyncio.gather(*tasks)
        
        if self.session:
            await self.session.close()
        
        return results

def print_banner():
    logo = f'''
  ,--.,--.      ,--.  ,--.          ,--.   
 ,-|  ||  |-.  ,-|  |,-'  '-. ,---.,-'  '-. 
' .-. || .-. '' .-. |'-.  .-'| .--''-.  .-' 
\\ `-' || `-' |\\ `-' |  |  |  \\ `--.  |  |   
 `---'  `---'  `---'   `--'   `---'  `--'   
            dbdtct — Web Debug Mode Detection Tool
            Created by: Youssef Lahouifi
            Supervised by : Redouan Korchiyne
            
[ Debug Mode Scanner - Test various methods to detect debug mode ]
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
    print(f"[*] Starting scan at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[*] Testing {len(urls)} target(s)")
    
    detector = DebugDetector(max_workers=args.workers)
    results = await detector.scan_urls(urls)

    # Print results
    vulnerable_count = 0
    for url, findings in results:
        if findings:
            vulnerable_count += 1
            print(f"\n[+] Potential Debug Mode Detected on {url}")
            for method, match in findings:
                print(f"    -> Technique: {method}")
                print(f"    -> Fingerprint: {match}")
        else:
            print(f"[-] No debug patterns found on {url}")

    scan_time = time.time() - start_time
    print(f"\n[*] Scan Summary:")
    print(f"    -> Completed in: {scan_time:.2f} seconds")
    print(f"    -> Targets scanned: {len(urls)}")
    print(f"    -> Vulnerable targets: {vulnerable_count}")
    print(f"    -> Success rate: {(vulnerable_count/len(urls))*100:.1f}%")

if __name__ == '__main__':
    asyncio.run(main())
