"""
test_submission.py — Run accessibility tests on 5 real websites for submission proof.
Uses the actual nova_engine.py pipeline (Nova Pro + Bedrock).
"""
import subprocess
import json
import os
from datetime import datetime

WEBSITES = [
    "https://wikipedia.org",
    "https://github.com",
    "https://bbc.co.uk",
    "https://airbnb.com",
    "https://spotify.com",
]

def run_tests():
    results = {
        "tested_at": datetime.now().isoformat(),
        "model": "amazon.nova-pro-v1:0",
        "extended_thinking": True,
        "web_grounding": True,
        "websites": {}
    }

    for url in WEBSITES:
        print(f"\nTesting {url}...")
        try:
            proc = subprocess.run(
                ["py", "-3.12", "nova_engine.py", "--url", url, "--type", "WCAG Accessibility Scan"],
                capture_output=True, text=True, timeout=120,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )

            stdout = proc.stdout
            json_start = stdout.find("---JSON_START---")
            json_end   = stdout.find("---JSON_END---")

            if json_start != -1 and json_end != -1:
                json_str = stdout[json_start + len("---JSON_START---"):json_end].strip()
                test_result = json.loads(json_str)
                results["websites"][url] = {
                    "status":        "success",
                    "score":         test_result["summary"]["score"],
                    "wcag_level":    test_result["summary"].get("wcag_level", "N/A"),
                    "issues_count":  len(test_result.get("issues", [])),
                    "critical":      sum(1 for i in test_result.get("issues", []) if i.get("severity") == "CRITICAL"),
                    "major":         sum(1 for i in test_result.get("issues", []) if i.get("severity") == "MAJOR"),
                }
                print(f"  ✅ Score: {results['websites'][url]['score']} | Level: {results['websites'][url]['wcag_level']}")
            else:
                raise ValueError("No JSON delimiters found in output")

        except Exception as e:
            results["websites"][url] = {"status": "error", "error": str(e)[:200]}
            print(f"  ❌ Error: {str(e)[:100]}")

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "submission_proof.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ Submission proof saved → submission_proof.json")
    print(f"{'='*50}")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run_tests()
