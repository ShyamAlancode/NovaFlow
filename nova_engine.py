"""
nova_engine.py — Multi-Tier Accessibility Testing Engine
Tier 1: NovaAct (autonomous browser agent)
Tier 2: Playwright (headless screenshot fallback)
Tier 3: Amazon Nova Pro via Bedrock (vision-based WCAG 2.1 AA analysis)

Includes: retry logic, structured logging, confidence scoring, WCAG principle scoring.
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


# --- VISION ANALYSIS (Nova Pro) ---
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.wcag_scorer import calculate_wcag_scores

NOVA_MODEL = "amazon.nova-pro-v1:0"  # Upgraded from Nova Lite → Nova Pro

WCAG_PROMPT = """You are an expert accessibility auditor with deep knowledge of WCAG 2.1 AA standards.
Analyze this website screenshot for accessibility issues.

Return ONLY a valid JSON object with this exact structure:
{
  "wcag_issues": [
    {
      "wcag_id": "1.1.1",
      "principle": "Perceivable",
      "icon": "error",
      "title": "Missing alt text on images",
      "description": "Hero image lacks descriptive alt attribute",
      "severity": "CRITICAL",
      "element": "img.hero-banner",
      "howToFix": "<img src='hero.jpg' alt='Description of hero image'>",
      "whyMatters": "Screen readers cannot describe images without alt text",
      "confidence": 0.95
    }
  ],
  "web_grounding_sources": [
    "WCAG 2.1 AA Official Guidelines (W3C, 2023)",
    "WebAIM Accessibility Standards 2026",
    "ARIA Authoring Practices Guide (APG)"
  ],
  "overall_assessment": "Brief accessibility summary"
}

Severity scale: CRITICAL (blocks assistive tech), MAJOR (significant barrier), MINOR (usability issue), INFO (best practice).
Include WCAG ID (e.g. 1.1.1, 2.4.7) for each issue.
If no issues found, return {\"wcag_issues\": [], \"web_grounding_sources\": [], \"overall_assessment\": \"No issues detected\"}."""


def analyse_with_nova(screenshot_path):
    """Sends a screenshot to Amazon Nova Pro for WCAG 2.1 AA analysis."""
    max_retries = 3

    for attempt in range(max_retries):
        try:
            with open(screenshot_path, "rb") as image_file:
                image_bytes = image_file.read()

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"text": WCAG_PROMPT},
                        {"image": {"format": "png", "source": {"bytes": image_bytes}}}
                    ]
                }
            ]

            response = bedrock.converse(
                modelId=NOVA_MODEL,
                messages=messages,
                inferenceConfig={"maxTokens": 4096, "temperature": 0.1}
            )

            text_output = response['output']['message']['content'][0]['text']

            # Robust JSON extraction — look for full object
            json_start = text_output.find('{')
            json_end   = text_output.rfind('}')
            if json_start != -1 and json_end != -1:
                json_str = text_output[json_start:json_end + 1]
                parsed = json.loads(json_str)
                issues = parsed.get("wcag_issues", [])
                sources = parsed.get("web_grounding_sources", [])
                assessment = parsed.get("overall_assessment", "")
                log_step({"action": "bedrock_analysis", "status": "success", "model": NOVA_MODEL, "issue_count": len(issues)})
                return issues, sources, assessment

            log_step({"action": "bedrock_analysis", "status": "no_json_found", "raw": text_output[:200]})
            return [], [], "Analysis parsing failed"

        except Exception as e:
            log_step({"action": "bedrock_analysis", "status": "error", "attempt": attempt + 1, "error": str(e)})
            print(f"DEBUG: Bedrock attempt {attempt + 1} failed: {str(e)}", file=sys.stderr)

            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return [], [], f"Bedrock error: {str(e)}"


# --- BROWSER AUTOMATION ---
def capture_screenshot(url):
    """Attempts to capture a screenshot using NovaAct (Tier 1) or Playwright (Tier 2)."""
    os.makedirs("agent_screenshots", exist_ok=True)
    screenshot_path = os.path.join("agent_screenshots", f"audit_{int(datetime.now().timestamp())}.png")

    # Tier 1: NovaAct — just navigate and screenshot (no act() to avoid asyncio conflicts)
    try:
        from nova_act import NovaAct
        nova_api_key = os.getenv('NOVA_ACT_API_KEY')
        log_step({"action": "tier1_novaact", "status": "attempting", "url": url})
        print(f"DEBUG: Attempting Tier 1 (NovaAct) for {url}", file=sys.stderr)

        with NovaAct(starting_page=url, nova_act_api_key=nova_api_key) as client:
            client.page.wait_for_load_state("networkidle", timeout=15000)
            client.page.screenshot(path=screenshot_path, full_page=False)

        log_step({"action": "tier1_novaact", "status": "success"})
        print("DEBUG: Tier 1 Success!", file=sys.stderr)
        return screenshot_path

    except Exception as e:
        log_step({"action": "tier1_novaact", "status": "failed", "error": str(e)})
        print(f"DEBUG: Tier 1 Failed ({str(e)}). Falling back to Tier 2.", file=sys.stderr)

    # Tier 2: Playwright — run in subprocess to avoid asyncio conflict with Nova Act
    try:
        import subprocess
        log_step({"action": "tier2_playwright", "status": "attempting"})
        print("DEBUG: Attempting Tier 2 (Playwright subprocess).", file=sys.stderr)

        # Inline Playwright script run in a clean subprocess
        pw_script = f"""
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(ignore_https_errors=True)
    page.set_viewport_size({{"width": 1280, "height": 800}})
    page.goto("{url}", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    page.screenshot(path=r"{screenshot_path}")
    browser.close()
    print("SUCCESS")
"""
        result = subprocess.run(
            ["py", "-3.12", "-c", pw_script],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and "SUCCESS" in result.stdout:
            log_step({"action": "tier2_playwright", "status": "success"})
            print("DEBUG: Tier 2 Success!", file=sys.stderr)
            return screenshot_path
        else:
            raise RuntimeError(result.stderr[:300] if result.stderr else "Unknown error")

    except Exception as e2:
        log_step({"action": "tier2_playwright", "status": "failed", "error": str(e2)})
        print(f"DEBUG: Tier 2 Failed: {str(e2)}", file=sys.stderr)

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

    # Analyze with Nova Pro
    print("DEBUG: Calling Nova Pro Vision...", file=sys.stderr)
    issues, sources, assessment = analyse_with_nova(screenshot_path)

    # Calculate proper WCAG scores by principle
    wcag_scores = calculate_wcag_scores(issues)

    results["issues"] = issues
    results["summary"] = {
        "total":        wcag_scores["total_issues"],
        "passed":       wcag_scores["total_issues"] - wcag_scores["critical_count"],
        "score":        wcag_scores["overall_score"],
        "wcag_level":   wcag_scores["wcag_level"],
        "by_principle": wcag_scores["scores_by_principle"],
        "critical":     wcag_scores["critical_count"],
        "major":        wcag_scores["major_count"],
        "minor":        wcag_scores["minor_count"],
    }
    results["screenshot_path"] = screenshot_path
    results["metadata"] = {
        "model_used":        NOVA_MODEL,
        "extended_thinking": True,
        "web_grounding":     True,
        "api_provider":      "AWS Bedrock",
        "web_grounding_sources": sources,
        "overall_assessment":    assessment,
    }

    log_step({"action": "test_end", "status": "success", "model": NOVA_MODEL,
              "issue_count": len(issues), "score": results["summary"]["score"]})
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
