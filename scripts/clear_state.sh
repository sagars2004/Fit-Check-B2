#!/bin/bash
set -e

# Change to the API directory where the database and .venv are located
cd "$(dirname "$0")/../services/api"

echo "Clearing local SQLite database..."
sqlite3 .data/fit_check.db "DELETE FROM garment_candidates; DELETE FROM garments; DELETE FROM duplicate_reviews; DELETE FROM uploads; DELETE FROM import_jobs;"
echo "Database cleared."

echo "Clearing B2 bucket..."
export B2_BUCKET=$(cat ../.env | grep B2_BUCKET | cut -d '=' -f2)
if [ -n "$B2_BUCKET" ]; then
    .venv/bin/b2 rm --recursive --versions "b2://$B2_BUCKET/"
    echo "B2 bucket cleared."
else
    echo "No B2_BUCKET found in .env."
fi

echo "Done! The wardrobe and review queue are fully reset."
