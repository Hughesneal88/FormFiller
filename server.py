import asyncio
import json
import os
import shutil
import sys

# Force Windows Proactor event loop policy to allow subprocesses (needed for Playwright)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Set custom browser download path inside project directory to avoid Windows AppData EPERM errors
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(BASE_DIR, "browsers")

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

import generator
import automation

app = FastAPI(title="Survey Auto-Filler API")

# Ensure directories exist
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

RECORDS_FILE = os.path.join(DATA_DIR, "records.json")
MAPPING_FILE = os.path.join(DATA_DIR, "mapping.json")
LOG_FILE = os.path.join(BASE_DIR, "automation.log")

# Global task pointer to track background automation run
active_automation_task = None
automation_running = False

class FetchSchemaRequest(BaseModel):
    url: str

class GenerateRequest(BaseModel):
    mapping: Dict[str, Any]
    count: int = 95

class SubmitRequest(BaseModel):
    url: str
    ids: List[int]
    headed: bool = True

class EditRecordRequest(BaseModel):
    id: int
    data: Dict[str, Any]

# Helper to read/write records
def load_records() -> List[Dict[str, Any]]:
    if not os.path.exists(RECORDS_FILE):
        return []
    try:
        with open(RECORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_records(records: List[Dict[str, Any]]):
    with open(RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

# Helper to read/write mapping
def load_mapping() -> Dict[str, Any]:
    if not os.path.exists(MAPPING_FILE):
        return {}
    try:
        with open(MAPPING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_mapping(mapping: Dict[str, Any]):
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2)

@app.get("/api/status")
def get_status():
    return {
        "status": "online",
        "automation_running": automation_running,
        "records_count": len(load_records()),
        "has_mapping": len(load_mapping()) > 0
    }

@app.post("/api/schema/fetch")
async def api_fetch_schema(request: FetchSchemaRequest):
    try:
        schema = await automation.fetch_schema(request.url)
        # Load existing mapping and merge/store schema in mapping
        mapping = load_mapping()
        mapping["_schema"] = schema
        
        # Pre-populate default mappings (Question 1 to Rule 1, Question 2 to Rule 2, etc.)
        # Based on index matching
        for q in schema:
            q_name = q["name"]
            idx = q["index"]
            # Map index to generator rule keys
            rule_key = f"q{idx}_ans"
            # Special keys override
            if idx == 1: rule_key = "q1_name"
            elif idx == 2: rule_key = "q2_phone"
            elif idx == 3: rule_key = "q3_gender"
            elif idx == 4: rule_key = "q4_age"
            elif idx == 9: rule_key = "q9_location"
            elif idx == 13: rule_key = "q13_num"
            elif idx == 16: rule_key = "q16_occupation"
            elif idx == 17: rule_key = "q17_experience"
            elif idx == 18: rule_key = "q18_role"
            elif idx == 19: rule_key = "q19_activity"
            elif idx == 22: rule_key = "q22_group"
            elif idx == 23: rule_key = "q23_status"
            elif idx == 24: rule_key = "q24_issue"
            elif idx == 26: rule_key = "q26_cost"
            elif idx == 27: rule_key = "q27_intensity"
            elif idx == 29: rule_key = "q29_freq"
            elif idx == 31: rule_key = "q31_level"
            elif idx == 33: rule_key = "q33_practice"
            elif idx == 35: rule_key = "q35_cause"
            elif idx == 36: rule_key = "q36_amount"
            elif idx == 38: rule_key = "q38_impact"
            elif idx == 42: rule_key = "q42_freq"
            elif idx == 45: rule_key = "q45_range"
            elif idx == 48: rule_key = "q48_priority"
            elif idx == 49: rule_key = "q49_challenges"
            elif idx == 50: rule_key = "q50_catch"
            elif idx == 51: rule_key = "q51_price"
            elif idx == 52: rule_key = "q52_income"
            elif idx == 53: rule_key = "q53_stability"
            elif idx == 54: rule_key = "q54_freq"
            elif idx == 57: rule_key = "q57_season"
            elif idx == 58: rule_key = "q58_season"
            elif idx == 65: rule_key = "q65_strength"
            elif idx == 66: rule_key = "q66_rating"
            elif idx == 67: rule_key = "q67_recommendations"
            elif idx == 71: rule_key = "q71_ans"
            elif idx == 72: rule_key = "q72_ans"
            elif idx == 78: rule_key = "q78_ans"
            elif idx == 79: rule_key = "q79_ans"
            
            if q_name not in mapping:
                mapping[q_name] = rule_key
                
        save_mapping(mapping)
        return {"success": True, "schema": schema, "mapping": mapping}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/data/generate")
def api_generate_data(request: GenerateRequest):
    try:
        # Save the updated mapping configuration
        save_mapping(request.mapping)
        
        # Generate new records
        records = generator.generate_dataset(request.count)
        save_records(records)
        return {"success": True, "count": len(records), "records": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/submissions")
def api_get_submissions():
    return load_records()

@app.post("/api/submissions/edit")
def api_edit_submission(request: EditRecordRequest):
    records = load_records()
    found = False
    for r in records:
        if r["id"] == request.id:
            # Update fields
            for k, v in request.data.items():
                r[k] = v
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Record not found")
    save_records(records)
    return {"success": True, "record": next(r for r in records if r["id"] == request.id)}

@app.post("/api/submissions/clear")
def api_clear_submissions():
    save_records([])
    return {"success": True}

async def run_automation_in_background(url: str, ids: List[int], headed: bool):
    global automation_running
    automation_running = True
    try:
        records = load_records()
        records_to_run = [r for r in records if r["id"] in ids]
        mapping = load_mapping()
        
        # Mark their state as Pending in local records
        for r in records:
            if r["id"] in ids:
                r["status"] = "Pending"
        save_records(records)
        
        # Run loop
        results = await automation.run_automation_loop(url, records_to_run, mapping, headed)
        
        # Merge results back into saved records
        current_records = load_records()
        results_map = {r["id"]: r["status"] for r in results}
        for r in current_records:
            if r["id"] in results_map:
                r["status"] = results_map[r["id"]]
        save_records(current_records)
        
    except Exception as e:
        automation.write_log(f"Critical error in automation thread: {str(e)}")
    finally:
        automation_running = False

@app.post("/api/submit/run")
def api_run_submit(request: SubmitRequest, background_tasks: BackgroundTasks):
    global automation_running
    if automation_running:
        raise HTTPException(status_code=400, detail="Automation is already running.")
        
    # Start task
    background_tasks.add_task(run_automation_in_background, request.url, request.ids, request.headed)
    return {"success": True, "message": "Automation started in the background."}

@app.get("/api/submit/logs")
def api_get_logs():
    if not os.path.exists(LOG_FILE):
        return {"logs": ""}
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            logs = f.read()
        return {"logs": logs}
    except Exception:
        return {"logs": "Error reading log file."}

# Route for loading UI
@app.get("/")
def get_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Survey Auto-Filler</h1><p>UI files not found. Check static/ directory.</p>")

# Mount static folder for CSS, JS and assets
app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
