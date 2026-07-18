import sys
import io
from contextlib import redirect_stdout
from pathlib import Path
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import List, Dict
import litellm
from crewai import LLM
from env_utils import get_hf_token

# Ensure root directory is in the path to import engine components
BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from storage.db import SQLiteGraphStore  # noqa: E402

# 🌟 UPDATED IMPORTS: Pointing to your newly renamed files!
from run_live_crewai import run_multi_agent_workflow  # noqa: E402
from run_live_autogen import run_autogen_workflow  # noqa: E402

app = FastAPI(
    title="Agent Replay API",
    description="Mission Control API for managing and replaying Agentic workflows.",
    version="1.0.0"
)

store = SQLiteGraphStore()

# ---------------------------------------------------------
# 1. UI DASHBOARD
# ---------------------------------------------------------
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

@app.get("/", summary="Load Mission Control Dashboard")
def read_root():
    return FileResponse(BASE_DIR / "static" / "index.html")

# ---------------------------------------------------------
# 2. AGENT MANAGEMENT APIs
# ---------------------------------------------------------
@app.get("/api/agents", response_model=List[Dict], summary="List Unique Agents")
def list_unique_agents():
    try:
        return store.get_unique_agents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents/{agent_id}", response_model=List[Dict], summary="Get Agent Version History")
def get_agent_history(agent_id: str):
    try:
        history = store.get_agent_history(agent_id)
        if not history:
            raise HTTPException(status_code=404, detail=f"No history found for agent: {agent_id}")
        return history
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Entire Agent")
def delete_entire_agent(agent_id: str):
    try:
        history = store.get_agent_history(agent_id)
        if not history:
            raise HTTPException(status_code=404, detail="Agent not found.")
        for record in history:
            store.delete(record["record_id"])
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# 3. TRACE / RUN EXECUTION APIs
# ---------------------------------------------------------
@app.get("/api/runs/{record_id}/graph", summary="Get Execution Graph Payload")
def get_version_graph(record_id: str):
    try:
        return store.load(record_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/runs/{record_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Specific Version")
def delete_run(record_id: str):
    try:
        try:
            store.load(record_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Execution record not found.")
        store.delete(record_id)
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------
# 🌟 THE REPLAY ENDPOINT (NOW WITH AUTOGEN ROUTING) 🌟
# ---------------------------------------------------------
@app.post("/api/runs/{record_id}/replay", summary="Trigger Engine Replay (Relaxed Mode)")
def replay_agent_run(record_id: str):
    try:
        loaded_graph = store.load(record_id)
        
        step_counter = {"current": 0}
        nodes_list = list(loaded_graph.nodes.values())

        def hydrated_interceptor(*args, **kwargs):
            from litellm import ModelResponse
            
            # 🔥 CHAOS MONKEY INJECTION 🔥
            # Let the first network call succeed, but crash the second one (midway through)
            if step_counter["current"] == 1:
                step_counter["current"] += 1 # Increment so we don't get stuck
                raise ConnectionError("🔥 CHAOS MONKEY: Simulated LLM Network Timeout! OpenAI API is down!")
            
            # NORMAL RELAXED LOGIC
            if step_counter["current"] < len(nodes_list):
                current_node = nodes_list[step_counter["current"]]
                step_counter["current"] += 1
                return ModelResponse(**current_node.output)
            else:
                raise RuntimeError("Replay Divergence: Agent requested more LLM calls than were recorded.")

        original_completion = litellm.completion
        output_buffer = io.StringIO()
        
        try:
            litellm.completion = hydrated_interceptor
            
            hf_token = get_hf_token()
            if not hf_token:
                raise RuntimeError("HF_TOKEN missing from environment.")
            
            with redirect_stdout(output_buffer):
                if "autogen" in record_id:
                    run_autogen_workflow(hf_token)
                else:
                    hf_llm = LLM(model="huggingface/Qwen/Qwen2.5-Coder-7B-Instruct", api_key=hf_token)
                    run_multi_agent_workflow(hf_llm)
                
            logs = output_buffer.getvalue()
            
            if hasattr(store, "increment_replay_count"):
                store.increment_replay_count(record_id)
            
            return {
                "status": "success",
                "message": f"Successfully replayed {record_id} with ZERO network calls! (Relaxed Mode)",
                "logs": logs
            }
            
        except Exception as inner_e:
            # 🌟 CAPTURE THE CRASH FOR THE UI 🌟
            # Instead of a 500 error, grab the logs written up to the crash point
            logs = output_buffer.getvalue()
            logs += f"\n\n❌ CRITICAL SYSTEM HALT: {str(inner_e)}"
            
            # Return HTTP 200 so the frontend Replay Panel can successfully render the red text
            return {
                "status": "error",
                "message": "Replay failed midway due to simulated error.",
                "logs": logs
            }
        finally:
            litellm.completion = original_completion
            
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ---------------------------------------------------------
# 4. SYSTEM APIs
# ---------------------------------------------------------
@app.get("/api/stats", summary="Get System Stats")
def get_system_stats():
    try:
        return {"total_execution_records": store.get_count()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/system/clear", status_code=status.HTTP_204_NO_CONTENT, summary="Nuke Database")
def clear_all_data():
    try:
        store.clear_all()
        return None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)