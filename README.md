# PSALM Framework Demo

A Gradio-based demo application for the PSALM (Probing Stylistic Appropriation in Large Language Models) framework.

## Overview

This demo provides an interactive interface to showcase the PSALM framework's capabilities for evaluating copyright infringement and stylistic appropriation in texts using various computational and LLM-based evaluators.

## Features

- **Multi-page Workflow**: Guided process through input, configuration, evaluation, and results
- **Predefined Examples**: Quick-start with curated example cases
- **Evaluator Categories**: Organized by Lexical, Stylistic, Narrative, and Exception types
- **LLM Configuration**: Flexible configuration for LLM-based evaluators
- **Concurrent Execution**: Parallel evaluation with rate limiting and error handling
- **Progress Tracking**: Real-time progress during evaluation
- **Detailed Results**: Overview and per-evaluator detailed analysis

## Quick Start

### Using uv

```bash
# Run the demo
uv run start

# Or using python directly
python start.py
```

### Using pip

```bash
# Install dependencies
pip install -e .

# Run the demo
python -m main
```

## Configuration

### Environment Variables

- `OPENAI_API_KEY`: API key for OpenAI models (required for LLM evaluators)
- Custom LLM configuration can be provided through the UI

### LLM Settings

- Base URL: API endpoint
- Model: Model name (default: gpt-4o-mini)
- Temperature: Controls randomness (0.0-2.0)
- Max Tokens: Response length limit
- Timeout: Request timeout in seconds

## Project Structure

```
PSALM-demo/
├── src/
│   ├── main.py                 # Entry point
│   ├── start.py                # Alternative entry point
│   └── psalm/
│       ├── __init__.py
│       ├── core/               # Core models
│       ├── evaluators/         # Evaluator implementations
│       └── ui/
│           ├── __init__.py
│           └── demo/
│               ├── __init__.py
│               ├── models.py        # Data models
│               ├── registry.py      # Evaluator discovery & categorization
│               ├── orchestrator.py  # Evaluation execution
│               ├── examples.py      # Predefined examples
│               └── pages.py         # Gradio UI pages
├── pyproject.toml
└── README.md
```

## Available Evaluators

### Lexical Evaluators
- **ROUGE**: Recall-Oriented Understudy for Gisting Evaluation
- **BLEU**: Bilingual Evaluation Understudy
- **Exact Match**: Exact text matching

### Stylistic Evaluators
- **Writing Style**: Analyzes writing style similarity
- **Narrative Voice**: Analyzes authorial voice consistency

### Narrative Evaluators
- **Character Similarity**: Character analysis
- **Plot Structure Similarity**: Plot analysis
- **Scene Sequence Similarity**: Scene structure analysis
- **World Building Similarity**: World-building analysis

### Exception Evaluators
- **Parody/Satire**: Parody and satire detection
- **Pastiche**: Pastiche detection
- **Quotation/Citation**: Quotation and citation analysis
- **Scenes a Faire**: Scenes a faire detection

## Usage

1. **Input Page**: Enter source and target texts, or select an example
2. **Configuration Page**: Select evaluators and configure LLM settings
3. **Evaluation Page**: Run the analysis with progress tracking
4. **Results Page**: View summary and detailed results for each evaluator

## Best Practices Implemented

- **DRY**: Reusable components and utilities
- **SOLID**: Modular design with single responsibility principle
- **Atomic Logic**: Small, focused functions with clear purposes
- **Decoupled Components**: Independent modules with clear interfaces
- **Error Handling**: Comprehensive error handling and validation
- **Concurrency**: Rate-limited parallel execution
- **Type Safety**: Type hints throughout the codebase

## Requirements

- Python 3.11+
- Gradio 6.14.0+
- Required dependencies listed in pyproject.toml

## License

This demo is provided as part of the PSALM framework for showcasing and demonstration purposes.
