"""
Quick standalone test to confirm:
1. Ollama is reachable at localhost:11434
2. The llama3.1:8b model responds
3. JSON parsing in our wrapper works correctly

Run this from the project root (same folder as this file):
    python test_llm_client.py
"""

from pipeline.llm_client import call_llm_json

def main():
    result = call_llm_json(
        system_prompt="You are a helpful assistant. Always respond with valid JSON only, no extra text.",
        user_prompt='Respond with a JSON object with two keys: "greeting" (a short hello message) and "confidence" (a number 1-5).',
    )

    print("Success:", result.success)
    print("Latency (seconds):", round(result.latency_seconds, 2))
    print("Raw response:", result.raw_response)
    print("Parsed JSON:", result.parsed_json)
    if not result.success:
        print("Error:", result.error)


if __name__ == '__main__':
    main()
