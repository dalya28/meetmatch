"""Run on the labeled jury profiles using an explicitly configured Anthropic key."""
import os
from evaluate import LABELS, evaluate, load_cases, matcher, read_labels
from claude_rank import rerank

if __name__ == "__main__":
    cases = load_cases()
    labels = {k: int(v["label"]) for k, v in read_labels(LABELS).items() if v["label"] != ""}
    key = os.environ["ANTHROPIC_API_KEY"]
    model = os.getenv("MEETMATCH_MODEL", "claude-haiku-5-5")
    def rank(c, ai):
        pool = matcher.recommend(c["q"], k=15, lang=c["lang"])
        picks = rerank(c["q"], pool, c["lang"], key, model) if ai else pool[:5]
        return [m.profile["id"] for m in picks]
    for ai in (False, True):
        scores = evaluate(lambda c: rank(c, ai), cases, labels)
        print(model if ai else "Baseline", {k: round(v, 3) for k, v in scores.items() if k != "per_case"})
