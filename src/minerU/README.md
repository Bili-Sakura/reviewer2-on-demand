# MinerU Paper Parser

A Python client for the MinerU API that can parse academic papers from URLs or local PDF files and output parsed markdown content.

## Features

- Parse papers from URLs (PDFs, DOCs, PPTs, images)
- Parse local PDF files by uploading them
- Support for OCR, formula recognition, and table recognition
- Multiple language support with auto-detection
- Progress tracking during parsing
- Automatic download and extraction of results
- Command-line interface for easy use

## Installation

1. Clone this repository:
```bash
git clone <repository-url>
cd reviewer2-on-demand
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your MinerU API key:
   - Get your API key from [MinerU](https://mineru.net/)
   - Create a `.env` file in the project root:
```bash
# .env file
MINERU_API_KEY=your_actual_api_key_here
```

## Usage

### Command Line Interface

#### Parse a paper from URL:
```bash
python src/minerU/minerU.py "https://example.com/paper.pdf" -o ./output
```

#### Parse a local PDF file:
```bash
python src/minerU/minerU.py "./papers/paper.pdf" -o ./output
```

#### Available options:
```bash
python src/minerU/minerU.py --help
```

Options:
- `-o, --output`: Output directory (default: current directory)
- `--is-ocr`: Enable OCR (default: True)
- `--enable-formula`: Enable formula recognition (default: True)
- `--enable-table`: Enable table recognition (default: True)
- `--language`: Document language (default: auto)
- `--model-version`: Model version v1 or v2 (default: v2)

### Python API

#### Parse from URL:
```python
from src.minerU.minerU import MinerUClient

client = MinerUClient()
output_file = client.parse_from_url(
    "https://example.com/paper.pdf",
    output_dir="./output",
    is_ocr=True,
    enable_formula=True,
    enable_table=True,
    language="auto",
    model_version="v2"
)
print(f"Output saved to: {output_file}")
```

#### Parse local file:
```python
from src.minerU.minerU import MinerUClient

client = MinerUClient()
output_file = client.parse_from_file(
    "./papers/paper.pdf",
    output_dir="./output",
    is_ocr=True,
    enable_formula=True,
    enable_table=True,
    language="auto",
    model_version="v2"
)
print(f"Output saved to: {output_file}")
```

## API Parameters

### Parsing Options

- **is_ocr**: Enable OCR functionality for scanned documents
- **enable_formula**: Enable mathematical formula recognition
- **enable_table**: Enable table structure recognition
- **language**: Document language (ch, en, auto, etc.)
- **model_version**: Choose between v1 and v2 models
- **page_ranges**: Specify page ranges (e.g., "1-10,15-20")

### Supported File Formats

- PDF (.pdf)
- Word documents (.doc, .docx)
- PowerPoint presentations (.ppt, .pptx)
- Images (.png, .jpg, .jpeg)

## Error Handling

The client handles common errors and provides informative error messages:

- API authentication errors
- File format/size limitations
- Network timeouts
- Parsing failures
- Task completion timeouts

## Rate Limits

- Maximum file size: 200MB
- Maximum pages per document: 600
- Daily quota: 2000 pages at highest priority
- Maximum 200 files per batch request

## Examples

### Basic usage with default settings:
```bash
python src/minerU/minerU.py "https://arxiv.org/pdf/2103.12345.pdf"
```

### Custom settings for research papers:
```bash
python src/minerU/minerU.py "./research_paper.pdf" \
    -o ./parsed_papers \
    --language en \
    --model-version v2 \
    --enable-formula \
    --enable-table
```

### Batch processing multiple files:
```python
from src.minerU.minerU import MinerUClient

client = MinerUClient()
files = ["./paper1.pdf", "./paper2.pdf", "./paper3.pdf"]

for file_path in files:
    try:
        output_file = client.parse_from_file(file_path, output_dir="./output")
        print(f"Successfully parsed {file_path} -> {output_file}")
    except Exception as e:
        print(f"Failed to parse {file_path}: {e}")
```

## Troubleshooting

### Common Issues

1. **API Key Error**: Ensure your `.env` file contains the correct `MINERU_API_KEY`
2. **File Size Limit**: Files must be under 200MB
3. **Page Limit**: Documents must have 600 pages or fewer
4. **Network Timeouts**: Some URLs (GitHub, AWS) may timeout due to network restrictions
5. **File Format**: Ensure your file has a supported extension

### Getting Help

- Check the MinerU API documentation: https://mineru.net/
- Verify your API key is valid and has sufficient quota
- Check file format and size requirements
- Monitor the logs for detailed error information

## License

This project is licensed under the MIT License - see the LICENSE file for details.
