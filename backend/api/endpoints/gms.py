from fastapi import APIRouter
from pydantic import BaseModel
from microscope.core.session import SESSION

router = APIRouter()

class GMSResult(BaseModel):
    id: int
    result: str

@router.get("/poll")
async def gms_poll():
    """DM calls this to grab the next queued command."""
    return SESSION.methods["gatan"].channel.poll_next()

@router.post("/result")
async def gms_result(result: GMSResult):
    """DM calls this to post back the result of a command."""
    return SESSION.methods["gatan"].channel.post_result(result.id, result.result)