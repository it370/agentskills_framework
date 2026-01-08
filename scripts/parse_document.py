#!/usr/bin/env python3
"""
Document Parser Script

This script demonstrates how to create an external script that works
with the action executor's 'script' type.

Interface:
- Input: JSON via stdin
- Output: JSON via stdout
- Exit code: 0 for success, non-zero for error
"""

import sys
import json
from pathlib import Path


def parse_document(document_path: str, document_type: str) -> dict:
    """
    Parse a document and extract information.
    
    This is a mock implementation. In production, you would use
    libraries like PyPDF2, python-docx, etc.
    """
    path = Path(document_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {document_path}")
    
    # Mock extraction (replace with actual parsing logic)
    if document_type.lower() == "pdf":
        # In reality: use PyPDF2 or pdfplumber
        return {
            "extracted_text": f"Mock extracted text from {path.name}",
            "metadata": {
                "author": "Unknown",
                "title": path.stem,
                "created_at": "2024-01-01"
            },
            "page_count": 5
        }
    
    elif document_type.lower() in ["docx", "doc"]:
        # In reality: use python-docx
        return {
            "extracted_text": f"Mock extracted text from Word document {path.name}",
            "metadata": {
                "author": "Unknown",
                "title": path.stem,
                "created_at": "2024-01-01"
            },
            "page_count": 3
        }
    
    else:
        # Generic text file
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        return {
            "extracted_text": text,
            "metadata": {
                "filename": path.name,
                "size_bytes": path.stat().st_size
            },
            "page_count": 1
        }


def main():
    """Main entry point for the script."""
    try:
        # Read input from stdin
        inputs = json.load(sys.stdin)
        
        # Extract parameters
        document_path = inputs.get('document_path')
        document_type = inputs.get('document_type', 'unknown')
        
        if not document_path:
            raise ValueError("Missing required parameter: document_path")
        
        # Process the document
        result = parse_document(document_path, document_type)
        
        # Output result to stdout
        json.dump(result, sys.stdout, indent=2)
        
        # Exit successfully
        sys.exit(0)
        
    except Exception as e:
        # Output error information
        error_result = {
            "error": str(e),
            "error_type": type(e).__name__
        }
        json.dump(error_result, sys.stderr, indent=2)
        
        # Exit with error code
        sys.exit(1)


if __name__ == "__main__":
    main()
