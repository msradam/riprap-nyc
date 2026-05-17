# Triton model_repository scaffold — Granite 3B on a Pi

This is the reference shape for serving Granite 4.1:3b via Triton's
Python backend, for deployments that standardize on the Triton API.
The actual production assets live in [msradam/riprap-triton](https://github.com/msradam/riprap-triton);
this file is the spec a Pi-class build would follow.

## Layout

```
model_repository/
  granite_reconciler/
    config.pbtxt
    1/
      model.py
      granite4.1-3b.Q4_K_M.gguf       (~2.0 GB)
  granite_planner/
    config.pbtxt
    1/
      model.py
      granite4.1-3b.Q4_K_M.gguf       (symlink to the same file)
```

## `granite_reconciler/config.pbtxt`

```
name: "granite_reconciler"
backend: "python"
max_batch_size: 0

input [
  { name: "INPUT_MESSAGES"  data_type: TYPE_STRING dims: [ 1 ] },
  { name: "MAX_TOKENS"      data_type: TYPE_INT32  dims: [ 1 ]
    optional: true }
]
output [
  { name: "OUTPUT_TEXT"     data_type: TYPE_STRING dims: [ 1 ] }
]

# CPU-only on the Pi. The Python backend spawns one Python process per
# `instance_group { count }` — keep it at 1 to avoid loading the model
# weights twice. Concurrency comes from llama.cpp's internal parallel
# slot mechanism (see model.py `n_parallel`).
instance_group [ { kind: KIND_CPU count: 1 } ]
```

## `granite_reconciler/1/model.py`

```python
import json
import triton_python_backend_utils as pb_utils
from llama_cpp import Llama


class TritonPythonModel:
    """Triton Python backend wrapping llama.cpp for Granite 4.1:3b GGUF.

    On the Pi we run with n_parallel=2 (matches OLLAMA_NUM_PARALLEL
    in the simpler Shape B deployment) and n_ctx=4096. The GGUF
    weights live next to this file in the version directory.
    """

    def initialize(self, args):
        self.llm = Llama(
            model_path=f"{args['model_repository']}/{args['model_version']}/granite4.1-3b.Q4_K_M.gguf",
            n_ctx=4096,
            n_threads=4,         # all 4 Pi 5 performance cores
            n_parallel=2,        # 2 concurrent generation slots
            verbose=False,
        )

    def execute(self, requests):
        responses = []
        for req in requests:
            messages_t = pb_utils.get_input_tensor_by_name(req, "INPUT_MESSAGES")
            messages = json.loads(messages_t.as_numpy()[0].decode())
            max_tokens_t = pb_utils.get_input_tensor_by_name(req, "MAX_TOKENS")
            max_tokens = (int(max_tokens_t.as_numpy()[0])
                          if max_tokens_t is not None else 400)
            out = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=0,
            )
            text = out["choices"][0]["message"]["content"]
            out_tensor = pb_utils.Tensor(
                "OUTPUT_TEXT",
                pb_utils.np.array([text.encode()], dtype=object),
            )
            responses.append(pb_utils.InferenceResponse(output_tensors=[out_tensor]))
        return responses

    def finalize(self):
        pass
```

## How Riprap talks to it

Riprap's existing LiteLLM router speaks OpenAI-compatible HTTP. Triton's
built-in `openai` HTTP frontend (available 24.04+) maps Triton models
to the OpenAI Chat Completions API automatically when the model name
matches.

```bash
# .env on the Pi
RIPRAP_LLM_PRIMARY=vllm
RIPRAP_LLM_BASE_URL=http://triton:8000/v1
RIPRAP_RECONCILER_MODEL=granite_reconciler
RIPRAP_OLLAMA_3B_TAG=granite_reconciler    # so the alias router resolves
RIPRAP_OLLAMA_8B_TAG=granite_reconciler    # ditto (one model serves both roles)
```

The router (`app/llm.py`) doesn't know it's Triton vs vLLM — both speak
OpenAI's `/v1/chat/completions`. The reconciler asks for `granite-3b`
or `granite-8b`; both get routed to the single `granite_reconciler`
model served by Triton.

## ARM64 build

```bash
# Triton on Pi needs the ARM build:
docker pull nvcr.io/nvidia/tritonserver:24.10-py3   # check NVIDIA NGC for ARM tags
docker run --rm -d --name triton \
  -p 8000:8000 -p 8001:8001 -p 8002:8002 \
  -v $(pwd)/model_repository:/models \
  nvcr.io/nvidia/tritonserver:24.10-py3 \
  tritonserver --model-repository=/models --backend-config=python,shm-default-byte-size=4194304
```

Note: ARM Triton builds are not always available; check NGC. If they
aren't, build Triton from source for ARM64 (substantial work) — at
which point Shape B (just Ollama) is the pragmatic answer.

## Trade-offs vs Ollama (Shape B)

| | Shape B (Ollama) | Shape C (Triton) |
|---|---|---|
| Container count | 1 | 1 |
| ARM support | Native, mature | Build complexity |
| Concurrency | OLLAMA_NUM_PARALLEL | llama.cpp n_parallel inside Python backend |
| Streaming | Yes (Ollama) | Via Triton's stream API or wrapper |
| Multi-model serving | One model per Ollama instance | Native (Triton's design) |
| Operational uniformity with prod | None | Same Triton API on Pi + MI300X |

Use Shape C only when the operational-uniformity argument outweighs
the build complexity. Otherwise Shape B is the right Pi default.
