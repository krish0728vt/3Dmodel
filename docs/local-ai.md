# Local AI With Ollama

SHAH INDUSTRIES can use Ollama for natural-language CAD without an OpenAI API
key. The AI still returns structured JSON only; SHAH validates that JSON against
the same typed schemas used by OpenAI before any CadQuery geometry is generated.
No model output is executed as Python.

## Windows Setup

1. Install Ollama from the official Ollama desktop installer.
2. Start Ollama. The desktop app or service should listen on:

```text
http://127.0.0.1:11434
```

3. Pull a local model. Recommended starting examples:

```powershell
ollama pull qwen2.5-coder:7b
ollama list
```

Other local models may work, including `qwen2.5:7b` and `llama3.1:8b`, but
quality varies. Treat the configured model as a normal local setting, not a
project requirement.

## Configure SHAH

Use `.env`:

```env
SHAH_AI_PROVIDER=ollama
SHAH_OLLAMA_URL=http://127.0.0.1:11434
SHAH_OLLAMA_MODEL=qwen2.5-coder:7b
SHAH_AI_TIMEOUT_SECONDS=120
OPENAI_API_KEY=
```

Or use non-secret local machine settings in `config/local.json`:

```json
{
  "ai_provider": "ollama",
  "ollama_url": "http://127.0.0.1:11434",
  "ollama_model": "qwen2.5-coder:7b",
  "ai_timeout_seconds": 120
}
```

Secrets such as `OPENAI_API_KEY` belong only in `.env`, never in
`config/local.json`.

Provider values:

- `ollama`: local AI through Ollama, no API key.
- `openai`: OpenAI provider, requires `OPENAI_API_KEY`.
- `none`: manual/deterministic mode; no AI calls.

Provider selection is intentional. If Ollama is selected and down, SHAH does not
silently fall back to OpenAI. If OpenAI is selected and the key is missing, SHAH
does not silently switch to Ollama.

## Verify

```powershell
python app.py ai status
python app.py ai models
python app.py doctor
```

The Tools drawer also shows the active provider, configured model, endpoint, and
a **Test AI connection** action.

## Test Prompts

After Ollama is ready, try:

```text
Create a 100 x 60 x 5 mm mounting plate.
Create a 100 x 60 x 5 mm mounting plate with four 5 mm holes 8 mm from each corner.
Create a 30 mm diameter spacer with an 8 mm hole and 10 mm height.
Create an open-top enclosure for a 70 x 45 mm PCB with 2 mm walls.
Create a plate with a centered 20 mm boss.
```

For edits:

```text
Make the plate 20 mm wider.
Increase the mounting holes to 6 mm.
Make the cylinder taller.
```

Ambiguous edits should ask for clarification rather than inventing a target.

## Safety Notes

- SHAH only calls the configured provider endpoint; prompts cannot choose a
  destination URL.
- The default Ollama endpoint is localhost.
- Non-local Ollama URLs are rejected by default to avoid accidental prompt
  forwarding.
- SHAH never installs Ollama, starts Ollama, or downloads models automatically.
