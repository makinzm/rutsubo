#!/usr/bin/env bash
# Record the demo as a terminal session and convert to MP4 for YouTube.
#
# Playback speed is increased so Claude's processing time doesn't feel slow.
# Recording uses --idle-time-limit to cap long silences.
#
# Usage:
#   bash scripts/record_demo.sh           # uses LLM_BACKEND=cli (default)
#   LLM_BACKEND=mock bash scripts/record_demo.sh   # fast mock run for testing

set -e

CAST_FILE="demo.cast"
MP4_FILE="rutsubo_demo.mp4"
SPEED="${DEMO_SPEED:-3}"          # playback speed multiplier (3x default)
IDLE_LIMIT="${IDLE_LIMIT:-2}"     # cap idle time to N seconds during recording
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  Rutsubo Demo Recorder"
echo "  LLM_BACKEND=${LLM_BACKEND:-cli}"
echo "  Playback speed: ${SPEED}x"
echo "=========================================="
echo ""
echo "Recording demo (this may take a few minutes with LLM_BACKEND=cli)..."
echo "Press Ctrl+C to abort."
echo ""

# Record terminal session
asciinema rec "$CAST_FILE" \
  --command "bash $SCRIPT_DIR/demo.sh" \
  --title "Rutsubo — AI Agent Competition Protocol" \
  --idle-time-limit "$IDLE_LIMIT" \
  --overwrite

echo ""
echo "Recording complete. Converting to MP4 at ${SPEED}x speed..."

# Convert cast → GIF → MP4
agg "$CAST_FILE" demo_raw.gif \
  --speed "$SPEED" \
  --idle-time-limit "$IDLE_LIMIT" \
  --theme monokai

ffmpeg -y \
  -i demo_raw.gif \
  -vf "scale=1280:-1:flags=lanczos,fps=30" \
  -c:v libx264 -preset slow -crf 20 -pix_fmt yuv420p \
  -movflags +faststart \
  "$MP4_FILE"

rm -f demo_raw.gif

echo ""
echo "=========================================="
echo "  Done!"
echo "  MP4: $MP4_FILE"
echo "  Cast: $CAST_FILE"
echo ""
echo "  Upload $MP4_FILE to YouTube,"
echo "  then paste the URL into the hackathon form."
echo "=========================================="
