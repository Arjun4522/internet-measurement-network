from fastapi import FastAPI
from pydantic import BaseModel
from agent.agent import Agent

app = FastAPI(title="Agent Control API")

class ModuleCommand(BaseModel):
    name: str

@app.get("/status")
async def get_status():
    return {"status": "running", "modules": []}  # Extendable

@app.post("/reload")
async def reload_module(cmd: ModuleCommand):
    return {"message": f"Module {cmd.name} reloaded (mock)"}

@app.post("/recover")
async def recover_module(cmd: ModuleCommand):
    return {"message": f"Recovery for {cmd.name} initiated (mock)"}
