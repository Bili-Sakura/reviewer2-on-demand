# Paper Review Pipeline

A high-level pipeline for end-to-end paper processing and review using MinerU parser and LLM reviewer, following the Hugging Face style design.

## Overview

The Paper Review Pipeline combines two powerful components:
1. **MinerU Parser**: Extracts structured markdown content from PDF papers and URLs
2. **LLM Reviewer**: Evaluates papers using AI models to assess suitability for top-tier ML conferences

This pipeline provides a streamlined workflow for researchers, reviewers, and conference organizers to efficiently process and evaluate research papers.

## Features

- **End-to-End Processing**: From paper input to review output in a single pipeline
- **Multiple Input Formats**: Support for URLs and local PDF files
- **Conference-Specific Standards**: Built-in standards for ICML, NeurIPS, ICLR, and AAAI
- **Flexible Configuration**: Customizable parsing and review parameters
- **Batch Processing**: Handle multiple papers efficiently
- **Multiple Output Formats**: JSON, Markdown, and text outputs
- **Error Handling**: Robust error handling with detailed logging
- **Configuration Persistence**: Save and load pipeline configurations

## Installation

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your API keys:
```bash
# .env file
MINERU_API_KEY=your_mineru_api_key_here
DASHSCOPE_API_KEY=your_dashscope_api_key_here
```

## Quick Start

### Basic Usage

```python
from pipelines import PaperReviewPipeline

# Initialize pipeline with default configuration
pipeline = PaperReviewPipeline()

# Review a paper from URL
result = pipeline(
    "https://arxiv.org/pdf/2103.12345.pdf",
    conference="neurips"
)

print(f"Assessment: {result['review']['parsed_review']['assessment']}")
print(f"Confidence: {result['review']['parsed_review']['confidence_score']}/10")
```

### Review Local PDF

```python
# Review a local PDF file
result = pipeline(
    "./papers/research_paper.pdf",
    conference="icml"
)
```

### Batch Processing

```python
# Process multiple papers
papers = [
    "https://arxiv.org/pdf/2103.12345.pdf",
    "https://arxiv.org/pdf/2104.56789.pdf",
    "./papers/local_paper.pdf"
]

results = pipeline(papers, conference="iclr")
```

## Configuration

### Default Configuration

The pipeline comes with sensible defaults, but you can customize every aspect:

```python
from pipelines import PaperReviewPipeline, PaperReviewConfig, MinerUConfig, LLMConfig

config = PaperReviewConfig(
    mineru=MinerUConfig(
        api_key="your_key",
        output_dir="./custom_output",
        enable_formula=True,
        enable_table=True
    ),
    llm=LLMConfig(
        model_name="qwen-plus",
        temperature=0.1,
        max_tokens=4000
    ),
    output_format="markdown"
)

pipeline = PaperReviewPipeline(config)
```

### Configuration Options

#### MinerU Configuration
- `api_key`: MinerU API key
- `is_ocr`: Enable OCR for scanned documents
- `enable_formula`: Enable mathematical formula recognition
- `enable_table`: Enable table structure recognition
- `language`: Document language (auto, en, ch, etc.)
- `model_version`: Parser model version (v1, v2)
- `output_dir`: Directory for parsed content
- `max_wait_time`: Maximum wait time for parsing (seconds)

#### LLM Configuration
- `model_name`: LLM model to use for review
- `api_key`: OpenRouter API key
- `temperature`: Generation temperature (0.0-1.0)
- `max_tokens`: Maximum tokens in response
- `system_prompt`: Custom system prompt for review
- `review_criteria`: List of review criteria

#### Pipeline Configuration
- `cache_dir`: Cache directory for models
- `device`: Device for computation (auto, cpu, cuda)
- `save_parsed_content`: Whether to save parsed content
- `save_review_results`: Whether to save review results
- `output_format`: Output format (json, markdown, txt)

## Conference Standards

The pipeline includes built-in standards for major ML conferences:

| Conference | Acceptance Rate | Min Confidence |
|------------|----------------|----------------|
| ICML       | 22%            | 7/10           |
| NeurIPS    | 20%            | 7/10           |
| ICLR       | 32%            | 6/10           |
| AAAI       | 25%            | 6/10           |

## Output Structure

### Review Results

```python
{
    "input": "paper_url_or_path",
    "conference": "neurips",
    "parsed_content": {
        "output_file": "path/to/parsed.md",
        "content": "parsed markdown content",
        "file_size": 15000,
        "parsing_config": {...}
    },
    "review": {
        "raw_response": "LLM raw response",
        "parsed_review": {
            "assessment": "Accept/Reject/Revision",
            "confidence_score": 8,
            "is_competitive": True,
            "conference_standards": {...}
        },
        "llm_config": {...}
    },
    "timestamp": "2024-01-15T10:30:00"
}
```

## Advanced Usage

### Custom Review Prompts

```python
config = PaperReviewConfig(
    llm=LLMConfig(
        system_prompt="""You are a specialized reviewer for computer vision papers.
        Focus on:
        - Novelty of the approach
        - Quality of experiments
        - Reproducibility
        - Impact on the field"""
    )
)
```

### Conference Comparison

```python
# Evaluate paper for multiple conferences
conferences = ["icml", "neurips", "iclr", "aaai"]
paper_url = "https://arxiv.org/pdf/2103.12345.pdf"

for conference in conferences:
    result = pipeline(paper_url, conference=conference)
    review = result['review']['parsed_review']
    print(f"{conference.upper()}: {review['assessment']} ({review['confidence_score']}/10)")
```

### Save and Load Configuration

```python
# Save pipeline configuration
pipeline.save_pretrained("./my_pipeline_config")

# Load pipeline from saved configuration
loaded_pipeline = PaperReviewPipeline.from_pretrained("./my_pipeline_config")
```

## Error Handling

The pipeline includes comprehensive error handling:

```python
try:
    result = pipeline("paper.pdf", conference="neurips")
except Exception as e:
    print(f"Pipeline failed: {e}")

# For batch processing, individual failures don't stop the pipeline
results = pipeline(["paper1.pdf", "paper2.pdf", "invalid.pdf"])
for result in results:
    if "error" in result:
        print(f"Failed: {result['error']}")
    else:
        print(f"Success: {result['review']['parsed_review']['assessment']}")
```

## Examples

See `examples.py` for comprehensive usage examples:

```bash
python pipelines/examples.py
```

## API Reference

### PaperReviewPipeline

#### `__init__(config=None, **kwargs)`
Initialize the pipeline with configuration.

#### `__call__(inputs, conference="auto", **kwargs)`
Process papers and generate reviews.

**Parameters:**
- `inputs`: Paper URL(s) or file path(s)
- `conference`: Target conference (icml, neurips, iclr, aaaai, auto)
- `**kwargs`: Additional parameters

**Returns:**
- Single paper: Dictionary with review results
- Multiple papers: List of dictionaries

#### `save_pretrained(save_directory)`
Save pipeline configuration to directory.

#### `from_pretrained(save_directory, **kwargs)`
Load pipeline from saved configuration.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Citation

If you use this pipeline in your research, please cite:

```bibtex
@software{paper_review_pipeline,
  title={Paper Review Pipeline: End-to-End Paper Processing and Review},
  author={Your Name},
  year={2024},
  url={https://github.com/yourusername/reviewer2-on-demand}
}
```

## Support

- **Issues**: Report bugs and feature requests on GitHub
- **Documentation**: See the code docstrings for detailed API documentation
- **Examples**: Check `examples.py` for usage patterns
- **Configuration**: Review `config.py` for all available options
