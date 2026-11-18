import os
from openai import OpenAI
# API_KEY = os.getenv("NVIDIA_API_KEY")
# if not API_KEY:
#     raise ValueError("❌ .env फ़ाइल में NVIDIA_API_KEY नहीं मिली!")

client = OpenAI(
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = "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"
)


completion = client.chat.completions.create(
  model="nvidia/nemotron-3.5-super-vl-120b-a12b",
  messages=[{"role": "user", "content": [{"type": "text", "text": "Read the traffic sign in this image. What does it say, and what color is the sign?"}, {"type": "image_url", "image_url": {"url": "https://assets.ngc.nvidia.com/products/api-catalog/phi-3-5-vision/example1a.jpg"}}]}],
  temperature=1,
  top_p=0.95,
  max_tokens=16384,

  parallel_tool_calls=True,



  seed=42,
  extra_body={"chat_template_kwargs": {"enable_thinking": True}},
  stream=True
)

for chunk in completion:
  if not chunk.choices:
    continue
  reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
  if reasoning:
    print(reasoning, end="")
  if chunk.choices[0].delta.content is not None:
    print(chunk.choices[0].delta.content, end="")