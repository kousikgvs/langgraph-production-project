import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from main import app as graph_app


class GenerateRequest(BaseModel):
	topic: str


app = FastAPI()


@app.post("/generate")
def generate(request: GenerateRequest):
	def event_stream():
		for update in graph_app.stream({"topic": request.topic}, stream_mode="updates"):
			yield f"data: {json.dumps(update)}\n\n"
		yield "data: [DONE]\n\n"

	return StreamingResponse(event_stream(), media_type="text/event-stream")