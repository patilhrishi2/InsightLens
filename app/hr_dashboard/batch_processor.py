from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import threading
import time
from parser.groq_fallback import call_groq_model
from parser.llm_structured_extractor import build_llm_prompt
from jd_parser.llm_9_parser import parse_jd_with_gemma
from resume_jd_comparator.comparison_engine import ResumeJDComparator
import json
import os
import random
import requests

# -------------------------
# Parallel Processing (ThreadPool)
# -------------------------
def process_resume_file(resume_text):
    prompt = build_llm_prompt(resume_text)
    structured_data, latency = call_groq_model(prompt)
    return structured_data

# -------------------------
# Exponential Backoff for Groq API
# -------------------------
def call_groq_model_with_backoff(prompt, max_retries=5):
    attempt = 0
    wait_time = 60  # Start with 60 seconds

    while attempt < max_retries:
        try:
            structured_data, latency = call_groq_model(prompt)
            return structured_data, latency

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"[WARNING] Rate limit hit. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                wait_time *= 2  # Exponential backoff
                attempt += 1
            else:
                raise e

        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            raise e

    print("[ERROR] Max retries exceeded for Groq API.")
    raise Exception("Max retries exceeded for Groq API.")


def parallel_file_processing(resume_files, jd_file, max_workers=5):
    results = []
    jd_json = None  # ✅ Add this to store the parsed JD

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []

        futures.append(executor.submit(parse_jd_with_gemma, jd_file))

        for file in resume_files:
            futures.append(executor.submit(process_resume_file, file))

        for future in as_completed(futures):
            try:
                result = future.result()

                # ✅ Extract JD JSON correctly
                if isinstance(result, dict) and 'parsed_output' in result:
                    jd_json = result['parsed_output']  # Only keep the JD JSON
                    continue  # Skip adding JD to results

                if isinstance(result, tuple):
                    structured_data, latency = result
                    print(f"[INFO] Resume processed in {latency:.2f} seconds")
                    results.append(structured_data)
                else:
                    results.append(result)

            except Exception as e:
                print(f"[ERROR] Exception during parallel processing: {e}")
                results.append(None)

    return results, jd_json  # ✅ Return JD JSON separately

# -------------------------
# Groq Token Rate Limiter
# -------------------------

class TokenRateLimiter:
    def __init__(self, max_tokens_per_minute):
        self.max_tokens_per_minute = max_tokens_per_minute
        self.tokens_used = 0
        self.lock = threading.Lock()
        self.reset_time = time.time() + 60

    def wait_for_slot(self, tokens_needed):
        with self.lock:
            current_time = time.time()
            if current_time >= self.reset_time:
                self.tokens_used = 0
                self.reset_time = current_time + 60

            if self.tokens_used + tokens_needed > self.max_tokens_per_minute:
                wait_time = self.reset_time - current_time
                print(f"[INFO] Token limit reached. Waiting for {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                self.tokens_used = 0
                self.reset_time = time.time() + 60

            self.tokens_used += tokens_needed
            print(f"[INFO] Tokens used this minute: {self.tokens_used}/{self.max_tokens_per_minute}")

# -------------------------
# Mistral Daily Request Tracker
# -------------------------

class DailyRequestTracker:
    def __init__(self, max_requests_per_day):
        self.max_requests_per_day = max_requests_per_day
        self.requests_made = 0
        self.lock = threading.Lock()
        self.reset_time = time.time() + 86400  # Reset after 24 hours

    def _check_reset(self):
        """Reset the counter if 24 hours have passed."""
        if time.time() >= self.reset_time:
            self.requests_made = 0
            self.reset_time = time.time() + 86400
            print("[INFO] Daily request tracker reset for new day.")

    def can_make_request(self):
        with self.lock:
            self._check_reset()
            return self.requests_made < self.max_requests_per_day

    def record_request(self):
        with self.lock:
            self._check_reset()
            if self.requests_made < self.max_requests_per_day:
                self.requests_made += 1
                print(f"[INFO] Mistral requests used today: {self.requests_made}/{self.max_requests_per_day}")
                return True
            else:
                print("[WARNING] Daily Mistral limit reached.")
                return False

# -------------------------
# Batch Processor
# -------------------------

class BatchProcessor:
    def __init__(self, token_limiter, request_tracker):
        self.queue = Queue()
        self.token_limiter = token_limiter
        self.request_tracker = request_tracker
        self.executor = ThreadPoolExecutor(max_workers=5)

    def add_task(self, resume_json, jd_json):
        self.queue.put((resume_json, jd_json))
        print(f"[INFO] Task added to queue. Current queue size: {self.queue.qsize()}")

    def run(self):
        while True:
            if not self.queue.empty():
                resume_json, jd_json = self.queue.get()

                estimated_tokens = len(str(resume_json)) // 4 + len(str(jd_json)) // 4

                self.token_limiter.wait_for_slot(estimated_tokens)

                if self.request_tracker.can_make_request():
                    self.executor.submit(self.process_comparison, resume_json, jd_json)
                    self.request_tracker.record_request()
                else:
                    print("[WARNING] Skipping task. Mistral request limit reached.")

            time.sleep(1)

    def process_comparison(self, resume_json, jd_json):
        try:
            if resume_json is None:
                print("[ERROR] Skipping comparison: Resume is None.")
                return  # Skip this task safely

            comparator = ResumeJDComparator(resume_json, jd_json)
            result = comparator.compare()
            print(f"[INFO] Comparison Result: {result}")

            # ✅ Save to JSON file (Append Mode)
            os.makedirs('batch_results', exist_ok=True)
            with open('batch_results/batch_output.json', 'a', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False)
                f.write('\n')  # Write each result on a new line

        except Exception as e:
            print(f"[ERROR] Exception during resume-JD comparison: {e}")

# -------------------------
# Batch Processor Runner
# -------------------------

def run_batch_processor():
    token_limiter = TokenRateLimiter(max_tokens_per_minute=6000)
    request_tracker = DailyRequestTracker(max_requests_per_day=50)
    processor = BatchProcessor(token_limiter, request_tracker)

    threading.Thread(target=processor.run, daemon=True).start()
    return processor
