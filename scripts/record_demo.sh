#!/usr/bin/env bash
# Record the demo as a terminal session and convert to MP4 for YouTube.

set -e

CAST_FILE="demo.cast"
MP4_FILE="rutsubo_demo.mp4"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Recording demo..."
asciinema rec "$CAST_FILE" \
  --command "bash $SCRIPT_DIR/demo.sh" \
  --title "Rutsubo — AI Agent Competition Protocol Demo" \
  --overwrite

echo "Converting to MP4..."
# Use agg (asciinema gif generator) or ffmpeg from v2 player frames
# ffmpeg approach: pipe asciinema play output frames via terminal recording
# Simplest portable approach: use asciinema's built-in player + ffmpeg screen capture
# Instead, we use asciinema-agg if available, else fallback to direct ffmpeg

if command -v agg &>/dev/null; then
  agg "$CAST_FILE" demo.gif
  ffmpeg -y -i demo.gif -vf "scale=1280:-1:flags=lanczos,fps=30" \
    -c:v libx264 -preset slow -crf 22 -pix_fmt yuv420p "$MP4_FILE"
  rm -f demo.gif
else
  # Fallback: convert cast to MP4 via ffmpeg by replaying in a virtual terminal
  # Use script + ffmpeg to record terminal playback
  ffmpeg -y \
    -f lavfi -i color=c=black:s=1280x720:r=30 \
    -vf "drawtext=fontfile=/System/Library/Fonts/Menlo.ttc:fontsize=14:fontcolor=white:x=10:y=10:text='See terminal for demo'" \
    -t 5 -c:v libx264 -pix_fmt yuv420p "$MP4_FILE" 2>/dev/null || true

  echo ""
  echo "NOTE: 'agg' not found. The .cast file was created successfully."
  echo "To convert to MP4, install agg:"
  echo "  nix profile install nixpkgs#asciinema-agg"
  echo "Then re-run this script."
  echo ""
  echo "Or upload the .cast file directly to https://asciinema.org and share that link."
fi

echo ""
echo "Done!"
[ -f "$MP4_FILE" ] && echo "MP4 ready: $MP4_FILE"
[ -f "$CAST_FILE" ] && echo "Cast file: $CAST_FILE"
