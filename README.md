# SHAH INDUSTRIES - Prompt-to-STEP CAD Generator

An AI-inspired CAD assistant that turns engineering prompts into validated parametric CAD specifications and STEP files.

SHAH CAD uses an original futuristic engineering identity: clean, technical, premium, and focused on reliable design automation. The SHAH INDUSTRIES branding is fictional and original. It is inspired by the broader idea of an advanced AI engineering assistant, but it is not affiliated with Marvel, Stark Industries, or any copyrighted franchise.

## Architecture

```text
Natural-language prompt
    -> OpenAI structured output
    -> Pydantic CAD specification
    -> geometry validation
    -> deterministic CadQuery generator
    -> STEP export
```

The LLM returns structured data only. It does not write CadQuery code, Python code, or STEP text. Geometry remains deterministic and owned by the local generator.

## Supported Parts

Milestone 3 supports six part types:

- `mounting_plate`: rectangular plate, rounded corners, through holes
- `box`: solid rectangular box with optional rounded vertical edges
- `cylinder`: solid cylinder with optional center through hole
- `spacer`: cylindrical spacer with required center through hole
- `l_bracket`: simple 90-degree bracket without face-specific holes
- `electronics_enclosure`: simple open-top enclosure with optional mounting posts

All dimensions are millimeters.

## Example Prompts

```text
Create a 100 x 60 x 5 mm mounting plate with four 5 mm holes 8 mm from each edge and 4 mm rounded corners.
```

```text
Create a solid box 100 mm wide, 60 mm deep and 25 mm tall. Round the vertical edges by 3 mm.
```

```text
Create a 30 mm diameter, 50 mm tall cylinder with a 10 mm through hole.
```

```text
Create a spacer 20 mm OD, 6 mm ID and 10 mm tall.
```

```text
Create an L bracket 60 mm wide, 40 mm tall, 30 mm deep and 4 mm thick.
```

```text
Create an open-top electronics enclosure with 70 x 45 mm internal dimensions, 25 mm high, 2 mm walls and a 2 mm bottom.
```

## Tech Stack

- Python
- CadQuery
- Pydantic
- OpenAI Python SDK
- python-dotenv
- pytest

## Repository Structure

```text
app.py                  CLI with natural-language and manual modes
ai/schemas.py           Pydantic schemas for every supported part type
ai/parser.py            OpenAI structured-output prompt parser
cad/validator.py        Geometry validation before CAD creation
cad/operations.py       Reusable CadQuery helper operations
cad/generator.py        Generic dispatch plus per-part CAD builders
outputs/                Generated STEP files
tests/                  pytest coverage for parser, CLI, validation, generation, and export
requirements.txt        Python dependencies
.env.example            API key template
```

## Setup

CadQuery can be environment-sensitive on Windows. Python 3.11 is recommended.

Using the existing project environment:

```powershell
.\.venv311\Scripts\python -m pip install -r requirements.txt
```

Or create a fresh Conda/Miniforge environment:

```powershell
conda create -n shah-cad python=3.11
conda activate shah-cad
conda install -c conda-forge cadquery
pip install openai pydantic pytest python-dotenv
```

## OpenAI Configuration

Natural-language mode reads the API key from `OPENAI_API_KEY`.

Create a local `.env` file from the template:

```powershell
Copy-Item .env.example .env
```

Then edit `.env`:

```text
OPENAI_API_KEY=your_api_key_here
```

`.env` is ignored by Git. Do not commit secrets.

Optionally set a model:

```text
OPENAI_MODEL=gpt-5-mini
```

## Run

```powershell
.\.venv311\Scripts\python app.py
```

The CLI offers two modes:

```text
1. Describe a part using natural language
2. Enter dimensions manually
```

Natural-language mode sends the prompt to the structured parser, displays the interpreted CAD spec, and asks for confirmation before export.

Manual mode lets you choose:

```text
1. Mounting plate
2. Box
3. Cylinder
4. Spacer
5. L bracket
6. Electronics enclosure
```

The default output path is preserved for compatibility:

```text
outputs/model.step
```

## Validation

Validation runs before CadQuery geometry generation. Invalid specs raise readable domain errors instead of silently correcting geometry.

Current checks include:

- Positive required dimensions
- Valid corner radii
- Hole diameters smaller than parent geometry
- Mounting plate holes fully inside plate bounds
- Spacer ID smaller than OD
- L bracket thickness compatible with leg dimensions
- Enclosure wall and bottom thickness
- Mounting posts inside the enclosure cavity
- Mounting post hole diameter smaller than post outside diameter

## Testing

```powershell
.\.venv311\Scripts\python -m pytest
```

Normal tests do not call the live OpenAI API. Parser tests mock structured AI responses.

Tests cover:

- Prompt parser dispatch for supported part types
- Unsupported and incomplete prompt handling
- Validation failures for each new part family
- Solid generation for every supported part
- STEP export for every supported part
- Existing mounting plate behavior
- Natural-language and manual CLI flows

## Current Limitations

- Units are millimeters only.
- L bracket holes are not implemented yet.
- Electronics enclosures are open-top only.
- No lids, snap fits, complex cutouts, countersinks, counterbores, or STL export yet.
- The project is not a general CAD agent; it supports the listed part families only.

## Roadmap

Milestone 4:

- Operation-based CAD system
- Extrusion
- Revolve
- Sweep
- Loft
- Shell
- Boolean operations
- Patterns
- Mirrors

Milestone 5:

- Conversational modification of existing parts
- Revision history
- Parameter editing

Milestone 6:

- SHAH INDUSTRIES futuristic web interface
- 3D viewer
- Prompt input
- Design inspector
- STEP/STL download

## Notes

Milestone 3 expands the part library while preserving the original pipeline: structured specification in, validated deterministic geometry out. The OpenAI parser can choose a supported schema, but the local code remains the authority for validation, construction, and export.
