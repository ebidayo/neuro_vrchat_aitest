def build_debate_response(claim_summary: str, counter_point: str) -> list:
    # Returns exactly 3 Japanese chunks
    return [
        f"なるほど、{claim_summary}という前提だね。",
        f"ただ、{counter_point}が説明されていない。",
        "だから、その主張は成り立たないと思う。"
    ]
