#!/bin/bash
# Usage: ./poster.sh <search_query> <output_filename>
# Searches Film.ru, TMDB, Wikipedia for movie poster
# Example: ./poster.sh "горничная" "the-housemaid.jpg"

QUERY="$1"
OUTPUT="$2"
IMG_DIR="$(dirname "$0")/img"
mkdir -p "$IMG_DIR"

if [ -z "$QUERY" ] || [ -z "$OUTPUT" ]; then
  echo "Usage: $0 <search_query> <output_filename>"
  exit 1
fi

OUT_PATH="$IMG_DIR/$OUTPUT"

# Helper: try download and check if valid image (>5KB)
try_download() {
  local url="$1"
  local tmp="/tmp/poster_test_$$"
  local code=$(curl -L -s -o "$tmp" -w "%{http_code}" "$url" 2>/dev/null)
  local size=$(stat -c%s "$tmp" 2>/dev/null || echo 0)
  if [ "$code" = "200" ] && [ "$size" -gt 5000 ]; then
    mv "$tmp" "$OUT_PATH"
    echo "OK: $url ($size bytes)"
    return 0
  fi
  rm -f "$tmp"
  return 1
}

# --- Method 1: Film.ru slug search ---
echo "=== Trying Film.ru ==="
# Transliterate query to slug (basic)
SLUG=$(echo "$QUERY" | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')

for suffix in "" "-0" "-1" "-2" "-3" "-4" "-5"; do
  URL="https://www.film.ru/movies/${SLUG}${suffix}"
  HTML=$(curl -L -s "$URL" -w "\n%{http_code}" 2>/dev/null)
  CODE=$(echo "$HTML" | tail -1)
  if [ "$CODE" = "200" ]; then
    # Extract og:image
    POSTER=$(echo "$HTML" | grep -oP 'og:image"\s*content="([^"]+)"' | grep -oP 'content="\K[^"]+' | head -1)
    if [ -n "$POSTER" ]; then
      # Get full-size version (remove /styles/.../public/)
      FULL_POSTER=$(echo "$POSTER" | sed 's|/styles/[^/]*/public/|/|')
      TITLE=$(echo "$HTML" | grep -oP '<title>\K[^<]+' | head -1)
      echo "  Found: $TITLE"
      echo "  Poster: $FULL_POSTER"
      if try_download "$FULL_POSTER"; then
        exit 0
      fi
      # Fallback to thumb version
      if try_download "$POSTER"; then
        exit 0
      fi
    fi
  fi
done

# --- Method 2: TMDB search ---
echo "=== Trying TMDB ==="
ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))" 2>/dev/null || echo "$QUERY")

# Search movies
TMDB_HTML=$(curl -L -s "https://www.themoviedb.org/search?query=$ENCODED" 2>/dev/null)
TMDB_PATH=$(echo "$TMDB_HTML" | grep -oP '/movie/[0-9]+-[^"]+' | head -1)
if [ -z "$TMDB_PATH" ]; then
  # Try TV
  TMDB_PATH=$(echo "$TMDB_HTML" | grep -oP '/tv/[0-9]+-[^"]+' | head -1)
fi

if [ -n "$TMDB_PATH" ]; then
  echo "  Found: $TMDB_PATH"
  TMDB_PAGE=$(curl -L -s "https://www.themoviedb.org$TMDB_PATH" 2>/dev/null)
  TMDB_IMG=$(echo "$TMDB_PAGE" | grep -oP 'https://image\.tmdb\.org/t/p/w500/[^"]+' | head -1)
  if [ -n "$TMDB_IMG" ]; then
    echo "  Poster: $TMDB_IMG"
    if try_download "$TMDB_IMG"; then
      exit 0
    fi
  fi
fi

# --- Method 3: Wikipedia ---
echo "=== Trying Wikipedia ==="
# Try English Wikipedia
for lang in "en" "ru"; do
  WIKI_ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$QUERY'))" 2>/dev/null || echo "$QUERY")
  WIKI_HTML=$(curl -L -s "https://${lang}.wikipedia.org/wiki/$WIKI_ENCODED" 2>/dev/null)
  WIKI_IMG=$(echo "$WIKI_HTML" | grep -oP '//upload\.wikimedia\.org/wikipedia/en/[a-f0-9]/[a-f0-9]{2}/[^"]+\.(jpg|jpeg|png)' | head -1)
  if [ -n "$WIKI_IMG" ]; then
    echo "  Found: https:$WIKI_IMG"
    if try_download "https:$WIKI_IMG"; then
      exit 0
    fi
  fi
done

echo "FAIL: No poster found for '$QUERY'"
exit 1
