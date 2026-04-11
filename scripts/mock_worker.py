"""
Mock worker agent server for demo purposes.
Starts a minimal FastAPI server on the given port that responds to POST /execute.
Quality level controls the response content (used by LLM_BACKEND=mock scorer).

Usage:
    python scripts/mock_worker.py <port> <quality> <name>
    e.g. python scripts/mock_worker.py 8101 0.9 HighQualityAgent
"""

import sys
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8101
quality = float(sys.argv[2]) if len(sys.argv) > 2 else 0.5
name = sys.argv[3] if len(sys.argv) > 3 else "WorkerAgent"

app = FastAPI()


class ExecuteRequest(BaseModel):
    subtask: str
    task_id: str = ""


@app.post("/execute")
def execute(req: ExecuteRequest):
    if quality >= 0.8:
        result = (
            f"[{name}] Complete solution for: {req.subtask}\n\n"
            "All requirements fully met with detailed implementation, "
            "proper error handling, and comprehensive test coverage. "
            f"QUALITY:{quality:.2f}"
        )
    elif quality >= 0.5:
        result = (
            f"[{name}] Partial solution for: {req.subtask}\n\n"
            "Core requirements addressed. Some edge cases may need further work. "
            f"QUALITY:{quality:.2f}"
        )
    else:
        result = (
            f"[{name}] Incomplete attempt for: {req.subtask}\n\n"
            "Basic structure provided but requirements not fully met. "
            f"QUALITY:{quality:.2f}"
        )
    return {"result": result}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")
