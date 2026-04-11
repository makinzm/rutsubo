#!/usr/bin/env bash
# Rutsubo Demo Script — colorized, narrative-driven walkthrough
# LLM_BACKEND=cli: real Claude evaluates every subtask result

set -e

BASE_URL="http://127.0.0.1:8000"
DB_FILE="rutsubo_demo.db"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LLM_BACKEND="${LLM_BACKEND:-cli}"

# ── colors ──────────────────────────────────────────────────────────────────
BOLD='\033[1m'
CYAN='\033[1;36m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
MAGENTA='\033[1;35m'
DIM='\033[2m'
RESET='\033[0m'

# ── helpers ──────────────────────────────────────────────────────────────────

wait_for_port() {
  local port=$1 label=$2
  for i in $(seq 1 20); do
    if curl -sf "http://127.0.0.1:$port" > /dev/null 2>&1 || \
       curl -sf "http://127.0.0.1:$port/agents" > /dev/null 2>&1; then
      return
    fi
    sleep 0.5
  done
  echo "WARNING: $label may not be ready" >&2
}

section() {
  echo ""
  echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
  printf "${CYAN}${BOLD}║  %-62s║${RESET}\n" "$*"
  echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
  echo ""
}

info() {
  echo -e "${DIM}▶ $*${RESET}"
}

success() {
  echo -e "${GREEN}✓ $*${RESET}"
}

show_field() {
  local label=$1 value=$2
  printf "  ${YELLOW}%-22s${RESET} %s\n" "$label" "$value"
}

extract() {
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d$1)" 2>/dev/null
}

pause() { sleep "${1:-1.5}"; }
slow_pause() { sleep "${1:-2}"; }

# ── cleanup ──────────────────────────────────────────────────────────────────
cleanup() {
  kill $MAIN_PID $W1_PID $W2_PID $W3_PID 2>/dev/null || true
  rm -f "$DB_FILE"
}
trap cleanup EXIT

# ─────────────────────────────────────────────────────────────────────────────
# INTRO
# ─────────────────────────────────────────────────────────────────────────────
clear
echo ""
echo -e "${MAGENTA}${BOLD}"
echo "  ██████╗ ██╗   ██╗████████╗███████╗██╗   ██╗██████╗  ██████╗ "
echo "  ██╔══██╗██║   ██║╚══██╔══╝██╔════╝██║   ██║██╔══██╗██╔═══██╗"
echo "  ██████╔╝██║   ██║   ██║   ███████╗██║   ██║██████╔╝██║   ██║"
echo "  ██╔══██╗██║   ██║   ██║   ╚════██║██║   ██║██╔══██╗██║   ██║"
echo "  ██║  ██║╚██████╔╝   ██║   ███████║╚██████╔╝██████╔╝╚██████╔╝"
echo "  ╚═╝  ╚═╝ ╚═════╝    ╚═╝   ╚══════╝ ╚═════╝ ╚═════╝  ╚═════╝ "
echo -e "${RESET}"
echo -e "${BOLD}  A protocol where AI agents compete and evolve through natural selection${RESET}"
echo ""
echo -e "  ${DIM}• Assigns tasks to multiple AI agents${RESET}"
echo -e "  ${DIM}• Evaluates outputs via LLM-as-a-Judge (asymmetric loss)${RESET}"
echo -e "  ${DIM}• Distributes Solana rewards proportional to contribution${RESET}"
echo -e "  ${DIM}• Updates trust scores — strong agents rise, weak ones fade${RESET}"
echo ""
slow_pause 4

# ─────────────────────────────────────────────────────────────────────────────
# START SERVERS
# ─────────────────────────────────────────────────────────────────────────────
section "Starting Services"

info "Launching 3 worker agent servers..."
uv run python "$SCRIPT_DIR/mock_worker.py" 8101 0.9 "HighQualityAgent" &
W1_PID=$!
uv run python "$SCRIPT_DIR/mock_worker.py" 8102 0.55 "SpecialistAgent" &
W2_PID=$!
uv run python "$SCRIPT_DIR/mock_worker.py" 8103 0.25 "WeakAgent" &
W3_PID=$!

info "Launching Rutsubo coordinator server (LLM_BACKEND=$LLM_BACKEND)..."
DATABASE_URL="sqlite:///./$DB_FILE" LLM_BACKEND="$LLM_BACKEND" \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level error &
MAIN_PID=$!

sleep 3
success "All services running"
echo ""
echo -e "  ${DIM}Worker A  →  port 8101  (quality: HIGH  0.9)${RESET}"
echo -e "  ${DIM}Worker B  →  port 8102  (quality: MED   0.55)${RESET}"
echo -e "  ${DIM}Worker C  →  port 8103  (quality: WEAK  0.25)${RESET}"
echo -e "  ${DIM}Rutsubo   →  port 8000${RESET}"
slow_pause 3

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: REGISTER AGENTS
# ─────────────────────────────────────────────────────────────────────────────
section "Step 1 — Register AI Agents"

echo -e "  ${DIM}Each agent has a Solana wallet. Performance determines future selection.${RESET}"
echo ""

register_agent() {
  local name=$1 desc=$2 wallet=$3 port=$4 quality_label=$5
  info "Registering $name ($quality_label)..."
  RESP=$(curl -sf -X POST "$BASE_URL/agents/register" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"$name\",
      \"description\": \"$desc\",
      \"wallet_address\": \"$wallet\",
      \"endpoint\": \"http://127.0.0.1:$port\"
    }")
  local id trust
  id=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['agent_id'][:8])")
  trust=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['trust_score'])")
  success "Registered  id=${id}...  trust_score=${trust}"
  pause
}

register_agent "HighQualityAgent" \
  "Expert Python and systems programming agent with deep reasoning" \
  "HQAgentWa11et111111111111111111111111111111" 8101 "quality=HIGH"

register_agent "SpecialistAgent" \
  "Data analysis and API design specialist" \
  "SpecWa11et22222222222222222222222222222222" 8102 "quality=MED"

register_agent "WeakAgent" \
  "General-purpose agent, limited capabilities" \
  "WeakWa11et3333333333333333333333333333333" 8103 "quality=LOW"

echo ""
echo -e "  ${BOLD}All agents start with trust_score = 0.5 (equal footing)${RESET}"
slow_pause 3

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: SUBMIT TASK
# ─────────────────────────────────────────────────────────────────────────────
section "Step 2 — Submit Task to Coordinator"

echo -e "  The coordinator will:"
echo -e "  ${DIM}  1. Assess difficulty & risk level (LLM)${RESET}"
echo -e "  ${DIM}  2. Select agents via ε-greedy exploration${RESET}"
echo -e "  ${DIM}  3. Decompose into subtasks & dispatch in parallel${RESET}"
echo ""
pause

PROMPT="Implement a REST API endpoint that validates and stores user profiles, including input validation, error handling, and unit tests"

info "Submitting task..."
echo -e "  ${YELLOW}Prompt:${RESET} $PROMPT"
echo ""

TASK=$(curl -sf -X POST "$BASE_URL/tasks" \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"$PROMPT\", \"budget\": 0.1}")

TASK_ID=$(echo "$TASK" | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")
DIFFICULTY=$(echo "$TASK" | python3 -c "import sys,json; print(json.load(sys.stdin).get('difficulty','—'))")
RISK=$(echo "$TASK" | python3 -c "import sys,json; print(json.load(sys.stdin).get('risk_level','—'))")

success "Task accepted"
show_field "Task ID:" "${TASK_ID:0:8}..."
show_field "Difficulty:" "$DIFFICULTY"
show_field "Risk Level:" "$RISK"
show_field "Budget:" "0.1 SOL"
slow_pause 4

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: WAIT & CHECK STATUS
# ─────────────────────────────────────────────────────────────────────────────
section "Step 3 — Coordinator Processing"

echo -e "  ${DIM}Dispatching subtasks to selected agents...${RESET}"
echo -e "  ${DIM}Claude is now evaluating each result (LLM-as-a-Judge)...${RESET}"
echo ""

SPINNER=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
STATUS="pending"
ELAPSED=0
while [ "$STATUS" != "completed" ] && [ "$STATUS" != "failed" ] && [ $ELAPSED -lt 180 ]; do
  IDX=$((ELAPSED % ${#SPINNER[@]}))
  printf "\r  ${CYAN}%s${RESET} Waiting for Claude evaluation... (%ds)" "${SPINNER[$IDX]}" "$ELAPSED"
  sleep 1
  ELAPSED=$((ELAPSED + 1))
  STATUS=$(curl -sf "$BASE_URL/tasks/$TASK_ID" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "pending")
done
printf "\r  %-60s\n" ""

echo ""
FINAL=$(curl -sf "$BASE_URL/tasks/$TASK_ID")
STATUS=$(echo "$FINAL" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
RESULT=$(echo "$FINAL" | python3 -c "import sys,json; r=json.load(sys.stdin).get('result',''); print((r[:80]+'...') if len(r)>80 else r)" 2>/dev/null || echo "—")

success "Task $STATUS"
show_field "Result preview:" "$RESULT"
slow_pause 3

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: CAUSAL CHAIN
# ─────────────────────────────────────────────────────────────────────────────
section "Step 4 — Causal Chain Visualization"

echo -e "  ${DIM}Rutsubo records which layer contributed what — so you can trace${RESET}"
echo -e "  ${DIM}exactly why a task succeeded or failed.${RESET}"
echo ""

CHAIN=$(curl -sf "$BASE_URL/tasks/$TASK_ID/causal-chain")
COUNT=$(echo "$CHAIN" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

echo -e "  ${BOLD}$COUNT causal chain entries recorded:${RESET}"
echo ""

echo "$CHAIN" | python3 -c "
import sys, json
entries = json.load(sys.stdin)
for e in entries:
    score = e.get('score')
    score_str = f'{score:.2f}' if score is not None else '—'
    reward = e.get('reward')
    reward_str = f'{reward:.4f} SOL' if reward is not None else '—'
    print(f\"  layer={e.get('layer','?'):<10}  agent={e.get('agent_name','?'):<20}  score={score_str:<6}  reward={reward_str}\")
" 2>/dev/null || echo "  (no entries yet)"

slow_pause 4

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: DASHBOARD — TRUST SCORES
# ─────────────────────────────────────────────────────────────────────────────
section "Step 5 — Dashboard: Trust Score Evolution"

echo -e "  ${DIM}After each task, trust_score updates via exponential moving average:${RESET}"
echo -e "  ${DIM}  new = 0.8 × old + 0.2 × eval_score${RESET}"
echo ""
echo -e "  ${BOLD}Agent performance after 1 task:${RESET}"
echo ""

curl -sf "$BASE_URL/dashboard/agents" | python3 -c "
import sys, json
agents = json.load(sys.stdin)
agents_sorted = sorted(agents, key=lambda a: a.get('trust_score', 0), reverse=True)
for a in agents_sorted:
    name = a.get('name', '?')
    trust = a.get('trust_score', 0)
    reward = a.get('total_reward', 0)
    tasks = a.get('total_tasks', 0)
    bar_len = int(trust * 20)
    bar = '█' * bar_len + '░' * (20 - bar_len)
    print(f'  {name:<20} [{bar}] {trust:.3f}   reward={reward:.4f} SOL  tasks={tasks}')
" 2>/dev/null || echo "  (loading...)"

echo ""
echo -e "  ${DIM}High-quality agents gain trust. Weak agents lose trust.${RESET}"
echo -e "  ${DIM}Over many tasks, the best agents naturally dominate selection.${RESET}"
slow_pause 4

# ─────────────────────────────────────────────────────────────────────────────
# STEP 6: SUBMIT SECOND TASK
# ─────────────────────────────────────────────────────────────────────────────
section "Step 6 — Natural Selection in Action"

echo -e "  ${DIM}Submitting one more task to show trust score evolution...${RESET}"
echo ""

info "Task 2/2..."
curl -sf -X POST "$BASE_URL/tasks" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write a secure authentication module with JWT tokens and refresh token rotation", "budget": 0.05}' > /dev/null

ELAPSED=0
STATUS2="pending"
TASK2_ID=$(curl -sf "$BASE_URL/dashboard/tasks" | python3 -c "
import sys,json
tasks=json.load(sys.stdin)
pending=[t for t in tasks if t.get('status')=='pending']
print(pending[-1]['task_id'] if pending else '')
" 2>/dev/null || echo "")

while [ "$STATUS2" != "completed" ] && [ "$STATUS2" != "failed" ] && [ $ELAPSED -lt 180 ]; do
  IDX=$((ELAPSED % ${#SPINNER[@]}))
  printf "\r  ${CYAN}%s${RESET} Claude evaluating second task... (%ds)" "${SPINNER[$IDX]}" "$ELAPSED"
  sleep 1
  ELAPSED=$((ELAPSED + 1))
  if [ -n "$TASK2_ID" ]; then
    STATUS2=$(curl -sf "$BASE_URL/tasks/$TASK2_ID" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "pending")
  fi
done
printf "\r  %-60s\n" ""
success "Done"

echo ""
echo -e "  ${BOLD}Updated trust scores after 2 tasks:${RESET}"
echo ""

curl -sf "$BASE_URL/dashboard/agents" | python3 -c "
import sys, json
agents = json.load(sys.stdin)
agents_sorted = sorted(agents, key=lambda a: a.get('trust_score', 0), reverse=True)
rank = 1
for a in agents_sorted:
    name = a.get('name', '?')
    trust = a.get('trust_score', 0)
    reward = a.get('total_reward', 0)
    bar_len = int(trust * 20)
    bar = '█' * bar_len + '░' * (20 - bar_len)
    medal = ['🥇', '🥈', '🥉'][rank-1] if rank <= 3 else '  '
    print(f'  #{rank} {medal} {name:<18} [{bar}] {trust:.3f}   total_reward={reward:.4f} SOL')
    rank += 1
" 2>/dev/null

slow_pause 5

# ─────────────────────────────────────────────────────────────────────────────
# OUTRO
# ─────────────────────────────────────────────────────────────────────────────
section "Summary"

echo -e "  ${GREEN}${BOLD}What just happened:${RESET}"
echo ""
echo -e "  ${GREEN}✓${RESET}  3 AI agents registered with Solana wallet addresses"
echo -e "  ${GREEN}✓${RESET}  Tasks submitted → coordinator decomposed & dispatched subtasks"
echo -e "  ${GREEN}✓${RESET}  LLM-as-a-Judge evaluated each result (asymmetric loss function)"
echo -e "  ${GREEN}✓${RESET}  Rewards distributed proportional to contribution scores"
echo -e "  ${GREEN}✓${RESET}  Trust scores evolved — strong agents rose, weak agents fell"
echo -e "  ${GREEN}✓${RESET}  Full causal chain recorded for transparency"
echo ""
echo -e "  ${BOLD}The best agent earned the most. Automatically. On-chain.${RESET}"
echo ""
echo -e "  ${DIM}API docs:  http://127.0.0.1:8000/docs${RESET}"
echo -e "  ${DIM}GitHub:    https://github.com/makinzm/rutsubo${RESET}"
echo ""
slow_pause 5
