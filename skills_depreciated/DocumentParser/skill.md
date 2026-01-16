---
name: DocumentParser
description: Parse documents using external Python script
requires:
  - document_path
  - document_type
produces:
  - extracted_text
  - metadata
  - page_count
executor: action

action:
  type: script
  script_path: ./scripts/parse_document.py
  interpreter: python
  timeout: 60.0
---

# DocumentParser

## Purpose
Execute an external Python script to parse documents (PDF, DOCX, etc.).
This demonstrates the `script` action type for running external processes.

## How It Works
1. Framework passes inputs as JSON via stdin
2. Script processes the document
3. Script outputs results as JSON via stdout
4. Framework captures and parses the output

## Script Interface
The script at `./scripts/parse_document.py` must:
- Read JSON from stdin
- Process according to inputs
- Write JSON to stdout
- Exit with code 0 on success

## Use Cases for Scripts
- Legacy code integration
- Language-specific processing (R, Julia, etc.)
- Binary/system tool invocation
- Heavy computational tasks
- File system operations

## Output Schema
- `extracted_text`: Full text content
- `metadata`: Document metadata (author, date, etc.)
- `page_count`: Number of pages

## Script Example
```python
#!/usr/bin/env python3
import sys
import json
import PyPDF2

# Read input
inputs = json.load(sys.stdin)
document_path = inputs['document_path']

# Process
with open(document_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    
    result = {
        "extracted_text": text,
        "metadata": {
            "author": reader.metadata.author,
            "title": reader.metadata.title
        },
        "page_count": len(reader.pages)
    }

# Output
json.dump(result, sys.stdout)
```

## Benefits
- Language agnostic
- Reuse existing tools
- Isolated execution
- Clear error handling
