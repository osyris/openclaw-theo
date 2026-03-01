#!/bin/bash
# Add a movie to the catalog
# Usage: ./add.sh <title> <year> <genres> <poster_file> [type] [status]
# Example: ./add.sh "Горничная" 2025 "Thriller,Drama" "the-housemaid.jpg" movie watchlist

TITLE="$1"
YEAR="$2"
GENRES="$3"       # comma-separated
POSTER="$4"       # filename in img/
TYPE="${5:-movie}" # movie or series
STATUS="${6:-watchlist}"

DIR="$(dirname "$0")"
JSON="$DIR/movies.json"

if [ -z "$TITLE" ] || [ -z "$YEAR" ] || [ -z "$POSTER" ]; then
  echo "Usage: $0 <title> <year> <genres> <poster_file> [type] [status]"
  exit 1
fi

# Build genre array
GENRE_JSON=$(echo "$GENRES" | tr ',' '\n' | sed 's/^ *//;s/ *$//' | awk '{printf "\"%s\",", $0}' | sed 's/,$//')

# Build new entry
NEW_ENTRY=$(cat <<EOF
{
    "title": "$TITLE",
    "year": $YEAR,
    "genre": [$GENRE_JSON],
    "poster": "img/$POSTER",
    "status": "$STATUS",
    "liked": false,
    "type": "$TYPE"
  }
EOF
)

# Add to JSON array (insert before last ])
if [ -f "$JSON" ]; then
  # Remove trailing ] and whitespace, add comma + new entry + ]
  python3 -c "
import json, sys
with open('$JSON','r') as f: data = json.load(f)
new = json.loads('''$NEW_ENTRY''')
data.append(new)
with open('$JSON','w') as f: json.dump(data, f, ensure_ascii=False, indent=2)
print(f'Added: {new[\"title\"]} ({new[\"year\"]}) — total {len(data)} items')
"
else
  echo "[$NEW_ENTRY]" > "$JSON"
  echo "Created catalog with: $TITLE"
fi
