import concurrent.futures
import contextlib
import queue
import threading
import time
import sys
import os
import re

from curl_cffi import requests as curl_requests
from cf_turnstile import TurnstileSolver

class DownloadManager:
    def __init__(self, links_file, max_workers=3, chunk_size=8*1024*1024):
        self.links_file = links_file
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.solver = TurnstileSolver()
        self.dl_session = curl_requests.Session(impersonate="chrome")
        self.total_links = 0
        self.completed_links = 0
        self.failed_links = []
        self.lock = threading.Lock()
        
        # Read links
        with open(links_file, 'r') as f:
            self.links = [line.strip() for line in f if line.strip()]
        self.total_links = len(self.links)

    def extract_direct_url(self, link):
        try:
            result = self.solver.get_direct_link(link)
            return result.get("direct_url"), result.get("cookies", {}), result.get("user_agent", "")
        except Exception as e:
            print(f"[!] Error extracting direct URL: {e}")
            return None, {}, ""

    def download_file(self, link):
        filename = link.split('#')[-1] if '#' in link else link.split('/')[-1]
        file_id = link.split('/')[-1].split('#')[0]
        
        dl_url, cookies, user_agent = self.extract_direct_url(link)
        if not dl_url:
            with self.lock:
                print(f"[!] Failed to get direct URL for {filename}")
                self.failed_links.append(link)
            return False

        try:
            # check if file exists and get its size
            initial_size = 0
            
            if os.path.exists(filename):
                initial_size = os.path.getsize(filename)
                
            # fetch headers to see total size and if it supports range
            headers = {}
            if user_agent:
                headers['User-Agent'] = user_agent
            head_req = self.dl_session.head(dl_url, cookies=cookies, headers=headers, allow_redirects=True)
            total_size = 0
            if 200 <= head_req.status_code < 300:
                try:
                    total_size = int(head_req.headers.get('content-length', 0))
                except (TypeError, ValueError):
                    total_size = 0
            
            if initial_size > 0 and initial_size == total_size:
                with self.lock:
                    print(f"[*] {filename} already fully downloaded.")
                    self.completed_links += 1
                return True
                
            resume_header = headers.copy()
            mode = 'wb'
            if initial_size > 0:
                resume_header['Range'] = f'bytes={initial_size}-'
                mode = 'ab'

            with contextlib.closing(self.dl_session.get(dl_url, stream=True, headers=resume_header, cookies=cookies)) as r:
                if r.status_code == 416 and initial_size > 0:
                    content_range = r.headers.get('content-range', '')
                    total_match = re.search(r'/([0-9]+)$', content_range)
                    if total_match and initial_size == int(total_match.group(1)):
                        with self.lock:
                            print(f"[*] {filename} already fully downloaded.")
                            self.completed_links += 1
                        return True
                if r.status_code not in (200, 206):
                    with self.lock:
                        print(f"[!] Failed to download {filename}, HTTP {r.status_code}")
                        self.failed_links.append(link)
                    return False
                
                if r.status_code == 200 and initial_size > 0:
                    # server ignores range header
                    mode = 'wb'
                    initial_size = 0
                
                dl = initial_size
                if total_size == 0:
                    content_range = r.headers.get('content-range', '')
                    total_match = re.search(r'/([0-9]+)$', content_range)
                    if total_match:
                        total_size = int(total_match.group(1))
                    else:
                        try:
                            total_size = int(r.headers.get('content-length', 0)) + initial_size
                        except (TypeError, ValueError):
                            total_size = 0
                    
                start_time = time.time()
                last_print = 0
                
                with open(filename, mode) as f:
                    for chunk in r.iter_content(chunk_size=self.chunk_size):
                        if chunk:
                            f.write(chunk)
                            dl += len(chunk)
                            
                            now = time.time()
                            if now - last_print > 1: # update progress every 1s
                                speed = (len(chunk)) / (now - last_print + 0.0001) / (1024*1024) if last_print > 0 else 0
                                percent = (dl / total_size) * 100 if total_size > 0 else 0
                                with self.lock:
                                    sys.stdout.write(f"\r[{filename}] {percent:.1f}% | {dl/(1024*1024):.1f}/{total_size/(1024*1024):.1f} MB | {speed:.1f} MB/s{' ' * 20}")
                                    sys.stdout.flush()
                                last_print = now
                                
                with self.lock:
                    sys.stdout.write(f"\r[{filename}] 100% | Downloaded successfully{' ' * 30}\n")
                    sys.stdout.flush()
                    self.completed_links += 1
                return True
                
        except Exception as e:
            with self.lock:
                print(f"\n[!] Error downloading {filename}: {e}")
                self.failed_links.append(link)
            return False

    def run(self):
        print(f"Starting download of {self.total_links} files with {self.max_workers} concurrent workers...")
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = [executor.submit(self.download_file, link) for link in self.links]
                concurrent.futures.wait(futures)
        finally:
            self.solver.stop()
            
        print("\n" + "="*50)
        print(f"Finished! Completed: {self.completed_links}/{self.total_links}")
        if self.failed_links:
            print("Failed links:")
            for link in self.failed_links:
                print(link)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        links_file = sys.argv[1]
    else:
        links_file = 'link.txt'
    
    manager = DownloadManager(links_file, max_workers=4)
    manager.run()
