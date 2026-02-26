"""
WCAG 2.1 AA Compliance Scorer
Maps raw Nova issues to WCAG principles and calculates structured scores.
"""

WCAG_PRINCIPLES = {
    "Perceivable": ["1.1.1", "1.2.1", "1.2.2", "1.3.1", "1.3.2", "1.4.1", "1.4.3", "1.4.4", "1.4.11"],
    "Operable":    ["2.1.1", "2.1.2", "2.2.1", "2.2.2", "2.3.1", "2.4.1", "2.4.2", "2.4.3", "2.4.4", "2.4.7"],
    "Understandable": ["3.1.1", "3.1.2", "3.2.1", "3.2.2", "3.3.1", "3.3.2", "3.3.3", "3.3.4"],
    "Robust":      ["4.1.1", "4.1.2", "4.1.3"],
}

SEVERITY_DEDUCTIONS = {
    "CRITICAL": 20,
    "MAJOR":    10,
    "MINOR":     4,
    "INFO":      1,
}


def calculate_wcag_scores(issues: list) -> dict:
    """
    Input:  List of issue dicts from Nova (each with wcag_id and severity).
    Output: Scores by principle + overall score + WCAG conformance level.
    """
    principle_issues = {p: [] for p in WCAG_PRINCIPLES}
    unclassified = []

    for issue in issues:
        wcag_id = issue.get("wcag_id", "")
        matched = False
        for principle, codes in WCAG_PRINCIPLES.items():
            if any(wcag_id.startswith(code) for code in codes):
                principle_issues[principle].append(issue)
                matched = True
                break
        if not matched:
            unclassified.append(issue)

    scores = {}
    for principle, p_issues in principle_issues.items():
        deduction = sum(
            SEVERITY_DEDUCTIONS.get(i.get("severity", "MINOR").upper(), 4)
            for i in p_issues
        )
        scores[principle] = max(0, 100 - deduction)

    overall = int(sum(scores.values()) / len(scores))

    if overall >= 90:
        wcag_level = "AAA - Enhanced"
    elif overall >= 75:
        wcag_level = "AA - Conformant"
    elif overall >= 55:
        wcag_level = "AA - Partially Conformant"
    else:
        wcag_level = "A - Partially Conformant"

    return {
        "scores_by_principle": scores,
        "overall_score": overall,
        "wcag_level": wcag_level,
        "total_issues": len(issues),
        "critical_count": sum(1 for i in issues if i.get("severity", "").upper() == "CRITICAL"),
        "major_count":    sum(1 for i in issues if i.get("severity", "").upper() == "MAJOR"),
        "minor_count":    sum(1 for i in issues if i.get("severity", "").upper() == "MINOR"),
        "unclassified_count": len(unclassified),
    }
