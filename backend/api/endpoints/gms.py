from fastapi import APIRouter
from pydantic import BaseModel
from microscope import gms_backend

router = APIRouter()

class GMSResult(BaseModel):
    id: int
    result: str

@router.get("/poll")
async def gms_poll():
    """DM calls this to grab the next queued command."""
    return gms_backend.poll_next()

@router.post("/result")
async def gms_result(result: GMSResult):
    """DM calls this to post back the result of a command."""
    return gms_backend.post_result(result.id, result.result)