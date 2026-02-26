"""
nova_engine.py — Multi-Tier Accessibility Testing Engine
Tier 1: NovaAct (autonomous browser agent)
Tier 2: Playwright (headless screenshot fallback)
Tier 3: Amazon Nova 2 Lite via Bedrock (vision-based WCAG analysis)

Includes: retry logic, structured logging, confidence scoring.
"""
import json
import os
import sys
import io
import argparse
import time
from datetime import datetime
import boto3
from dotenv import load_dotenv
import urllib3

# --- SETUP ---
# Prevent Windows terminal crashes from emojis in Nova's output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv(dotenv_path=os.path.join(os.getcwd(), 'novaflow', '.env.local'))
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))
load_dotenv()

bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=os.getenv('AWS_REGION', 'us-east-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    verify=False
)


# --- LOGGING ---
LOG_DIR = "logs"

def log_step(step_data: dict):
    """Appends a structured JSON log entry to a per-run log file."""
    os.makedirs(LOG_DIR, exist_ok=True)
    filename = os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d')}.jsonl")
    entry = {
        "timestamp": datetime.now().isoformat(),
        **step_data
    }
    with open(filename, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")


# --- VISION ANALYSIS ---
def analyse_with_nova(screenshot_path):
    """Sends a screenshot to Amazon Nova 2 Lite for WCAG analysis with confidence scoring."""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            with open(screenshot_path, "rb") as image_file:
                image_bytes = image_file.read()

            prompt = """
            Analyze this screenshot of a website for WCAG 2.1 AA accessibility issues.
            Return ONLY a valid JSON array of objects. Each object must have these fields:
            - "icon": "error" or "warning" or "info"
            - "title": short issue name
            - "description": what's wrong
            - "howToFix": code or instructions to fix
            - "whyMatters": why this matters for accessibility
            - "confidence": a float between 0.0 and 1.0 representing how confident you are

            If no issues are found, return an empty array: []
            """

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt},
                        {"image": {"format": "png", "source": {"bytes": image_bytes}}}
                    ]
                }
            ]

            response = bedrock.converse(
                modelId="amazon.nova-lite-v1:0",
                messages=messages,
                inferenceConfig={"maxTokens": 4096, "temperature": 0.2}
            )

            text_output = response['output']['message']['content'][0]['text']

            # Robust JSON extraction
            json_start = text_output.find('[')
            json_end = text_output.rfind(']')
            if json_start != -1 and json_end != -1:
                json_str = text_output[json_start:json_end + 1]
                issues = json.loads(json_str)
                log_step({"action": "bedrock_analysis", "status": "success", "issue_count": len(issues)})
                return issues

            log_step({"action": "bedrock_analysis", "status": "no_json_found", "raw": text_output[:200]})
            return []

        except Exception as e:
            log_step({"action": "bedrock_analysis", "status": "error", "attempt": attempt + 1, "error": str(e)})
            print(f"DEBUG: Bedrock attempt {attempt + 1} failed: {str(e)}", file=sys.stderr)

            if attempt < max_retries - 1:
                wait = 2 ** attempt
                time.sleep(wait)
            else:
                return []


# --- BROWSER AUTOMATION ---
def capture_screenshot(url):
    """Attempts to capture a screenshot using NovaAct (Tier 1) or Playwright (Tier 2)."""
    os.makedirs("agent_screenshots", exist_ok=True)
    screenshot_path = os.path.join("agent_screenshots", f"audit_{int(datetime.now().timestamp())}.png")

    # Tier 1: NovaAct
    try:
        from nova_act import NovaAct
        log_step({"action": "tier1_novaact", "status": "attempting", "url": url})
        print(f"DEBUG: Attempting Tier 1 (NovaAct) for {url}", file=sys.stderr)

        client = NovaAct(starting_page=url)
        client.start()
        client.page.screenshot(path=screenshot_path)
        client.stop()

        log_step({"action": "tier1_novaact", "status": "success"})
        print("DEBUG: Tier 1 Success!", file=sys.stderr)
        return screenshot_path

    except Exception as e:
        log_step({"action": "tier1_novaact", "status": "failed", "error": str(e)})
        print(f"DEBUG: Tier 1 Failed ({str(e)}). Falling back to Tier 2.", file=sys.stderr)

    # Tier 2: Playwright with retry
    max_retries = 2
    for attempt in range(max_retries):
        try:
            from playwright.sync_api import sync_playwright
            log_step({"action": "tier2_playwright", "status": "attempting", "attempt": attempt + 1})

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(ignore_https_errors=True)
                page.set_viewport_size({"width": 1280, "height": 800})
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.screenshot(path=screenshot_path)
                browser.close()

            log_step({"action": "tier2_playwright", "status": "success"})
            print("DEBUG: Tier 2 Success!", file=sys.stderr)
            return screenshot_path

        except Exception as e2:
            log_step({"action": "tier2_playwright", "status": "failed", "attempt": attempt + 1, "error": str(e2)})
            print(f"DEBUG: Tier 2 attempt {attempt + 1} failed: {str(e2)}", file=sys.stderr)

            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None


# --- MAIN TEST RUNNER ---
def run_accessibility_test(url, test_type="WCAG Accessibility Scan"):
    """Orchestrates the full test pipeline: capture → analyze → report."""
    log_step({"action": "test_start", "url": url, "test_type": test_type})

    results = {
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "issues": [],
        "summary": {"passed": 0, "total": 25, "score": 0}
    }

    screenshot_path = capture_screenshot(url)

    if screenshot_path is None:
        results["error"] = "Full Engine Failure: Could not capture screenshot via any tier."
        log_step({"action": "test_end", "status": "engine_failure"})
        return results

    # Analyze the screenshot with Nova 2 Lite
    print("DEBUG: Calling Nova Vision...", file=sys.stderr)
    issues = analyse_with_nova(screenshot_path)
    results["issues"] = issues
    results["summary"] = {
        "passed": max(0, 25 - len(issues)),
        "total": 25,
        "score": int(((25 - len(issues)) / 25) * 100)
    }
    results["screenshot_path"] = screenshot_path

    log_step({"action": "test_end", "status": "success", "issue_count": len(issues), "score": results["summary"]["score"]})
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NovaFlow Accessibility Engine")
    parser.add_argument("--url", required=True, help="Target URL to audit")
    parser.add_argument("--type", default="WCAG Accessibility Scan", help="Test type")
    args = parser.parse_args()

    try:
        output = run_accessibility_test(args.url, args.type)
        print("---JSON_START---")
        print(json.dumps(output, default=str))
        print("---JSON_END---")
    except Exception as e:
        error_json = json.dumps({"error": f"Serialization Error: {str(e)}", "url": args.url})
        print("---JSON_START---")
        print(error_json)
        print("---JSON_END---")
        sys.exit(1)
