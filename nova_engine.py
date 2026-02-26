import json
import os
import sys
import argparse
import asyncio
from datetime import datetime
import boto3
from dotenv import load_dotenv
import urllib3

# Suppress insecure request warnings for Bedrock verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Load environment variables
# Attempt to load from multiple potential locations for robustness
load_dotenv(dotenv_path=os.path.join(os.getcwd(), 'novaflow-web', '.env.local'))
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))
load_dotenv()

# Initialize AWS Bedrock client
bedrock = boto3.client(
    service_name='bedrock-runtime',
    region_name=os.getenv('AWS_REGION', 'us-east-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    verify=False 
)

def analyse_with_nova(screenshot_path):
    try:
        with open(screenshot_path, "rb") as image_file:
            image_bytes = image_file.read()

        prompt = """
        Analyze this screenshot of a website for WCAG 2.1 AA accessibility issues.
        Return ONLY a JSON array of objects with these fields: {icon, title, description, howToFix, whyMatters}.
        If no issues are found, return [].
        """

        # Using converse API for better structured handling
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
            inferenceConfig={"maxTokens": 2048, "temperature": 0.2}
        )
        
        text_output = response['output']['message']['content'][0]['text']
        
        # Robust JSON extraction
        json_match_start = text_output.find('[')
        json_match_end = text_output.rfind(']')
        if json_match_start != -1 and json_match_end != -1:
            json_str = text_output[json_match_start:json_match_end+1]
            return json.loads(json_str)
        return []
    except Exception as e:
        print(f"DEBUG: Bedrock Error: {str(e)}", file=sys.stderr)
        return []

def run_accessibility_test(url, test_type="WCAG Accessibility Scan"):
    results = {
        "url": url,
        "timestamp": datetime.now().isoformat(),
        "issues": [],
        "summary": {"passed": 0, "total": 25, "score": 0}
    }

    os.makedirs("agent_screenshots", exist_ok=True)
    screenshot_path = os.path.join("agent_screenshots", f"audit_{int(datetime.now().timestamp())}.png")

    success = False
    # 🟢 TRY TIER 1: NovaAct (Requested Library)
    try:
        from nova_act import NovaAct
        print(f"DEBUG: Attempting Tier 1 (NovaAct) for {url}", file=sys.stderr)
        client = NovaAct(starting_page=url)
        client.start()
        client.page.screenshot(path=screenshot_path)
        client.stop()
        print("DEBUG: Tier 1 Success!", file=sys.stderr)
        success = True
    except Exception as e:
        print(f"DEBUG: Tier 1 Failed ({str(e)}). Falling back to Tier 2 (Playwright).", file=sys.stderr)
        
        # 🟢 TRY TIER 2: Basic Playwright (More Robust)
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(ignore_https_errors=True)
                page.set_viewport_size({"width": 1280, "height": 800})
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.screenshot(path=screenshot_path)
                browser.close()
                print("DEBUG: Tier 2 Success!", file=sys.stderr)
                success = True
        except Exception as e2:
            print(f"DEBUG: Tier 2 Failed: {str(e2)}", file=sys.stderr)
            results["error"] = f"Full Engine Failure: {str(e2)}"
            return results

    if success:
        # 🔴 ANALYZE VISUALS
        print("DEBUG: Calling Nova Vison...", file=sys.stderr)
        issues = analyse_with_nova(screenshot_path)
        results["issues"] = issues
        results["summary"] = {
            "passed": max(0, 25 - len(issues)),
            "total": 25,
            "score": int(((25 - len(issues)) / 25) * 100)
        }
        results["screenshot_path"] = screenshot_path

    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--type", default="WCAG Accessibility Scan")
    args = parser.parse_args()

    # Final execution with safe serialization and clear delimiters
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
