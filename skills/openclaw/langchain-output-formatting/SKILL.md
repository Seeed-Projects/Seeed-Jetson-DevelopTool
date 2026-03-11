---
name: langchain-output-formatting
description: Format LLM output using Langchain on Jetson for structured smart home control signals. Deploys a local chatbot with Gradio UI that uses LlamaCpp and Langchain's StructuredOutputParser to produce JSON-formatted responses. Requires JetPack 5.0+ and a GGUF model.
---

# Format LLM Output with Langchain on Jetson

Use Langchain's StructuredOutputParser to constrain LLM output into structured JSON for smart home control. The chatbot runs locally on Jetson using LlamaCpp with a Gradio web interface.

---

## Execution model

Run one phase at a time. After each phase:
- Relay all output to the user.
- If output contains `[STOP]` → stop, consult the failure decision tree.
- If output ends with `[OK]` → tell the user "Phase N complete" and proceed.

---

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| Hardware | Jetson device (e.g. reComputer J4012) |
| JetPack | 5.0+ |
| Model | Llama 2 7B Chat GGUF (Q4_0 quantization) |
| Python | pip3 available |

---

## Phase 1 — Install dependencies (~3 min)

```bash
pip3 install --no-cache-dir --verbose "langchain[llm]" openai
pip3 install --no-cache-dir --verbose gradio==3.38.0
```

`[OK]` when both packages install without error.
`[STOP]` if pip3 fails — check Python version and pip availability.

---

## Phase 2 — Download GGUF model (~5–15 min)

Download the Llama 2 7B Chat GGUF model (Q4_0 quantization) from Hugging Face:

```bash
mkdir -p ~/models
# Download llama-2-7b-chat.Q4_0.gguf from Hugging Face
# Example using wget or huggingface-cli:
pip3 install huggingface-hub
huggingface-cli download TheBloke/Llama-2-7B-Chat-GGUF llama-2-7b-chat.Q4_0.gguf --local-dir ~/models
```

Verify:

```bash
ls -lh ~/models/llama-2-7b-chat.Q4_0.gguf
```

`[OK]` when the GGUF file exists (~3.8 GB).
`[STOP]` if download fails — check network and disk space.

---

## Phase 3 — Create the chatbot script

Create `format_opt.py` with the following content. The script uses Langchain's `StructuredOutputParser` with `ResponseSchema` to define output fields (user_input, suggestion, control signal, temperature), then wraps a LlamaCpp model in a Gradio chat interface:

```bash
cat > format_opt.py << 'PYEOF'
import copy
import gradio as gr
from langchain.llms import LlamaCpp
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.prompts import PromptTemplate

class ChatBot:
    def __init__(self, llama_model_path, history_length=3):
        self.chat_history = []
        self.history_threshold = history_length
        self.llm = LlamaCpp(
            model_path=llama_model_path,
            temperature=0.75,
            max_tokens=2000,
            top_p=1
        )
        response_schemas = [
            ResponseSchema(name="user_input", description="This is the user's input"),
            ResponseSchema(name="suggestion", type="string", description="your suggestion"),
            ResponseSchema(name="control", description="This is your response"),
            ResponseSchema(name="temperature", type="int",
                           description="Degrees centigrade temperature of the air conditioner.")
        ]
        self.output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
        self.format_instructions = self.output_parser.get_format_instructions()
        self.template = """
            Now you are a smart speaker, and you need to determine whether to turn on the air conditioner based on the user's input.
            In the suggestion section, please reply normal conversation.
            In the control section, if you need to turn on the air conditioner, please reply with <1>; if you need to turn off the air conditioner, please reply with <0>.
            {format_instructions}
            Please do not generate any comments.
            % USER INPUT:
            {user_input}
            YOUR RESPONSE:
        """
        self.prompt = PromptTemplate(
            input_variables=["user_input"],
            partial_variables={"format_instructions": self.format_instructions},
            template=self.template
        )

    def format_chat_prompt(self, message):
        prompt = ""
        for turn in self.chat_history:
            user_message, bot_message = turn
            prompt = f"{prompt}\nUser: {user_message}\nAssistant: {bot_message}"
        prompt = f"{prompt}\nUser: {message}\nAssistant:"
        return prompt

    def respond(self, message):
        prompt = self.prompt.format(user_input=message)
        formatted_prompt = self.format_chat_prompt(prompt)
        bot_message = self.llm(formatted_prompt)
        if len(self.chat_history) >= self.history_threshold:
            del self.chat_history[0]
        self.chat_history.append((message, bot_message))
        return "", self.chat_history

    def run_webui(self):
        with gr.Blocks() as demo:
            gr.Markdown("# Format Output of LLM Demo")
            chatbot = gr.Chatbot(height=500)
            msg = gr.Textbox(label="Prompt")
            btn = gr.Button("Submit")
            clear = gr.ClearButton(components=[msg, chatbot], value="Clear console")
            btn.click(self.respond, inputs=[msg], outputs=[msg, chatbot])
            msg.submit(self.respond, inputs=[msg], outputs=[msg, chatbot])
        gr.close_all()
        demo.launch()

if __name__ == '__main__':
    chatbot_ins = ChatBot("/home/nvidia/models/llama-2-7b-chat.Q4_0.gguf")
    chatbot_ins.run_webui()
PYEOF
```

Update the model path in the script to match your actual GGUF location.

`[OK]` when file is created.

---

## Phase 4 — Run the chatbot (~1 min to start)

```bash
python3 format_opt.py
```

Open a browser and navigate to `http://<jetson-ip>:7861/`.

Test by typing prompts like "It's really hot today" — the LLM should respond with structured JSON containing control signals.

`[OK]` when the Gradio UI loads and the LLM returns formatted JSON output.
`[STOP]` if the model fails to load or Gradio crashes.

---

## Failure decision tree

| Symptom | Action |
|---------|--------|
| `pip3 install langchain` fails | Upgrade pip: `pip3 install --upgrade pip`. Check Python ≥ 3.8. |
| `ModuleNotFoundError: llama_cpp` | Install: `pip3 install llama-cpp-python`. May need `CMAKE_ARGS="-DLLAMA_CUBLAS=on"` for GPU. |
| Model loading OOM | Use a smaller quantization (Q2_K) or free memory. Check with `free -h`. |
| Gradio won't start on port 7861 | Port in use. Kill existing process or set `demo.launch(server_port=7862)`. |
| LLM output not valid JSON | Adjust temperature lower (0.3–0.5). Ensure format_instructions are in the prompt. |
| Browser can't reach Jetson | Check firewall: `sudo ufw allow 7861`. Verify IP with `hostname -I`. |

---

## Reference files

- `references/source.body.md` — Full Seeed Wiki tutorial with code examples, screenshots, and next steps for Riva integration (reference only)
