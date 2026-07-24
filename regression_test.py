"""
regression_test.py
-------------------
A lightweight accuracy check for the deployed (or local) BMTC chatbot.

Define test cases as: a question, a list of phrases that MUST appear
somewhere in the answer (facts you know are true), and a list of phrases
that must NOT appear (facts you know are false / hallucinated). Run this
after every content or prompt change to catch regressions before real
users see them.

Usage:
    python regression_test.py --url http://localhost:8000
    python regression_test.py --url https://bmtc-rag-chatbot.onrender.com
"""
import argparse
import sys
import requests

# ---------------------------------------------------------------------------
# EDIT THIS LIST: add one entry per fact you want to guard.
# must_contain / must_not_contain checks are case-insensitive substring checks.
# Leave a list empty ([]) if there's nothing to assert for that side.
# ---------------------------------------------------------------------------
TEST_CASES = [
    {
        "question": "What can I do in the Client Portal?",
        "must_contain": [],       # fill in with phrases you KNOW are true
        "must_not_contain": [],   # fill in with phrases you KNOW are false
    },
    {
        "question": "How do I register as a test center?",
        "must_contain": [],
        "must_not_contain": [],
    },
    {
        "question": "What is the capital of France?",
        "must_contain": ["couldn't find", "knowledge base"],  # should refuse, not answer
        "must_not_contain": ["paris"],
    },
]


def run_tests(base_url: str):
    passed, failed = 0, 0

    for i, case in enumerate(TEST_CASES, 1):
        question = case["question"]
        try:
            resp = requests.post(
                f"{base_url}/chat",
                json={"question": question},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("answer", "")
        except Exception as e:
            print(f"[{i}] ERROR calling API for '{question}': {e}")
            failed += 1
            continue

        answer_lower = answer.lower()
        problems = []

        for phrase in case["must_contain"]:
            if phrase.lower() not in answer_lower:
                problems.append(f"MISSING expected phrase: '{phrase}'")

        for phrase in case["must_not_contain"]:
            if phrase.lower() in answer_lower:
                problems.append(f"FOUND forbidden phrase: '{phrase}'")

        if problems:
            failed += 1
            print(f"[{i}] FAIL — Q: {question}")
            print(f"     A: {answer[:300]}")
            for p in problems:
                print(f"     ✗ {p}")
        else:
            passed += 1
            print(f"[{i}] PASS — Q: {question}")

    print(f"\n{passed} passed, {failed} failed out of {len(TEST_CASES)} test cases.")
    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regression-test the BMTC chatbot's answers")
    parser.add_argument("--url", default="http://localhost:8000", help="Base URL of the running API")
    args = parser.parse_args()

    ok = run_tests(args.url.rstrip("/"))
    sys.exit(0 if ok else 1)
