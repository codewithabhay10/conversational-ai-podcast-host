"""
Night Research Crawler (MVP)
Fetches trending topics from Hacker News and Reddit.
Twitter/X is excluded — snscrape no longer works reliably.
Saves results to topics.json for morning pickup.

Run this before bed:
    python research.py
"""
import json
import os
import logging
import time
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


def fetch_hackernews(days=10, max_results=30):
    """Fetch top stories from Hacker News via Algolia API (free, no auth)."""
    import requests

    results = []
    try:
        # Algolia search API — search stories from last N days
        timestamp = int((datetime.now() - timedelta(days=days)).timestamp())
        url = (
            f"http://hn.algolia.com/api/v1/search?"
            f"tags=story&numericFilters=created_at_i>{timestamp}"
            f"&hitsPerPage={max_results}&query=technology OR AI OR programming"
        )
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])

        for hit in hits:
            results.append({
                "source": "hackernews",
                "title": hit.get("title", ""),
                "url": hit.get("url", ""),
                "points": hit.get("points", 0),
                "comments": hit.get("num_comments", 0),
                "date": hit.get("created_at", ""),
            })

        log.info(f"Fetched {len(results)} stories from Hacker News")
    except Exception as e:
        log.error(f"Hacker News fetch failed: {e}")

    return results


def fetch_reddit(subreddits=None, limit=30):
    """
    Fetch top posts from Reddit using the public JSON API (no auth required).
    Falls back gracefully if PRAW is not configured.
    """
    import requests

    if subreddits is None:
        from config import REDDIT_SUBREDDITS
        subreddits = REDDIT_SUBREDDITS

    results = []
    headers = {"User-Agent": "AI-Podcast-Buddy/1.0"}

    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/top.json?t=week&limit={limit}"
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            posts = resp.json().get("data", {}).get("children", [])

            for post in posts:
                d = post.get("data", {})
                results.append({
                    "source": f"reddit/r/{sub}",
                    "title": d.get("title", ""),
                    "url": f"https://reddit.com{d.get('permalink', '')}",
                    "score": d.get("score", 0),
                    "comments": d.get("num_comments", 0),
                    "selftext": (d.get("selftext", "") or "")[:300],
                })

            log.info(f"Fetched {len(posts)} posts from r/{sub}")
            time.sleep(1)  # Be nice to Reddit
        except Exception as e:
            log.error(f"Reddit fetch failed for r/{sub}: {e}")

    return results


def rank_and_extract_topics(hn_results, reddit_results, top_n=5):
    """
    Rank all results by engagement, extract top N topics.
    Returns list of topic dicts.
    """
    all_items = []

    # Normalize scoring
    for item in hn_results:
        all_items.append({
            "title": item["title"],
            "source": item["source"],
            "url": item.get("url", ""),
            "score": item.get("points", 0) + item.get("comments", 0) * 2,
            "summary": "",
        })

    for item in reddit_results:
        all_items.append({
            "title": item["title"],
            "source": item["source"],
            "url": item.get("url", ""),
            "score": item.get("score", 0) + item.get("comments", 0) * 2,
            "summary": item.get("selftext", "")[:200],
        })

    # Sort by engagement score
    all_items.sort(key=lambda x: x["score"], reverse=True)

    # Deduplicate by similar titles
    seen = set()
    unique = []
    for item in all_items:
        key = item["title"].lower()[:50]
        if key not in seen:
            seen.add(key)
            unique.append(item)

    topics = unique[:top_n]

    # Generate simple summaries
    for i, topic in enumerate(topics):
        if not topic["summary"]:
            topic["summary"] = f"Trending on {topic['source']}: {topic['title']}"
        topic["id"] = i + 1

    return topics


def generate_summaries_with_llm(topics):
    """
    Use Ollama to generate short conversational summaries for each topic.
    Falls back to basic summary if Ollama is unavailable.
    """
    from llm.llm import chat, check_ollama

    if not check_ollama():
        log.warning("Ollama not available, using basic summaries.")
        return topics

    for topic in topics:
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a research assistant. Summarize the following topic in 2-3 sentences, making it interesting and conversational. Focus on why someone should care about this."
                },
                {
                    "role": "user",
                    "content": f"Topic: {topic['title']}\nSource: {topic['source']}\nContext: {topic.get('summary', '')}"
                }
            ]
            summary = chat(messages)
            if summary:
                topic["summary"] = summary
        except Exception as e:
            log.error(f"Summary generation failed for '{topic['title']}': {e}")

    return topics


def save_topics(topics, filepath=None):
    """Save topics to JSON file."""
    if filepath is None:
        from config import TOPICS_FILE
        filepath = TOPICS_FILE

    data = {
        "fetched_at": datetime.now().isoformat(),
        "topic_count": len(topics),
        "topics": topics,
    }

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    log.info(f"Saved {len(topics)} topics to {filepath}")
    return filepath


def load_topics(filepath=None):
    """Load topics from JSON file."""
    if filepath is None:
        from config import TOPICS_FILE
        filepath = TOPICS_FILE

    if not os.path.exists(filepath):
        log.warning(f"No topics file found at {filepath}")
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        topics = data.get("topics", [])
        fetched = data.get("fetched_at", "unknown")
        log.info(f"Loaded {len(topics)} topics (fetched: {fetched})")
        return topics
    except Exception as e:
        log.error(f"Failed to load topics: {e}")
        return []


def run_research():
    """Full research pipeline. Run this nightly."""
    print("=" * 50)
    print("🌙 Night Research Crawler Starting...")
    print("=" * 50)

    # Fetch from sources
    print("\n📰 Fetching Hacker News...")
    hn = fetch_hackernews()

    print("📱 Fetching Reddit...")
    reddit = fetch_reddit()

    # Rank and extract
    print("\n🏆 Ranking topics...")
    topics = rank_and_extract_topics(hn, reddit, top_n=5)

    if not topics:
        print("❌ No topics found. Check your internet connection.")
        return

    # Generate summaries
    print("🧠 Generating summaries...")
    topics = generate_summaries_with_llm(topics)

    # Save
    filepath = save_topics(topics)
    print(f"\n✅ Saved {len(topics)} topics to {filepath}")

    print("\n📋 Topics for tomorrow:")
    for t in topics:
        print(f"  {t['id']}. {t['title']}")
        print(f"     {t['summary'][:100]}...")
        print()

    print("Done! Run 'python main.py' in the morning to start the podcast.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run_research()
