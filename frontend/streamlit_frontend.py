import json
import os
from typing import Iterable

import requests
import streamlit as st


BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


def parse_sse_lines(lines: Iterable[str]):
	for line in lines:
		if line.startswith("data: "):
			payload = line.removeprefix("data: ").strip()
			if payload == "[DONE]":
				return
			yield payload


def stream_generate(topic: str):
	response = requests.post(
		f"{BACKEND_URL}/generate",
		json={"topic": topic},
		stream=True,
		timeout=300,
	)
	response.raise_for_status()

	for payload in parse_sse_lines(response.iter_lines(decode_unicode=True)):
		yield json.loads(payload)


st.set_page_config(page_title="Streaming Generator", page_icon="💬", layout="centered")
st.title("Streaming Chat Generator")
st.caption("Send a topic and receive streamed updates from the backend.")

if "messages" not in st.session_state:
	st.session_state.messages = []

for message in st.session_state.messages:
	with st.chat_message(message["role"]):
		st.markdown(message["content"])

topic = st.chat_input("Enter a topic to generate content")

if topic:
	st.session_state.messages.append({"role": "user", "content": topic})
	with st.chat_message("user"):
		st.markdown(topic)

	assistant_placeholder = st.chat_message("assistant")
	streamed_text = []

	with assistant_placeholder:
		output_box = st.empty()
		try:
			for update in stream_generate(topic):
				for node_output in update.values():
					if isinstance(node_output, dict):
						chunk = node_output.get("content") or node_output.get("critique") or ""
						if chunk:
							streamed_text.append(chunk)
							output_box.markdown("".join(streamed_text))
		except requests.RequestException as error:
			output_box.error(f"Failed to stream response: {error}")
			st.stop()

	final_text = "".join(streamed_text).strip()
	if final_text:
		st.session_state.messages.append({"role": "assistant", "content": final_text})
