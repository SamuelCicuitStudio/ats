import os
import pdfplumber
from docx import Document
import re
import json
from jsonschema import validate
import ollama
from tqdm import tqdm
from langdetect import detect
from typing import Dict, Any, List
from pathlib import Path
import logging
import tkinter as tk
from tkinter import filedialog

# Configuration
OLLAMA_MODEL = "phi3:latest"
MAX_TOKENS = 3000

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CVParser:
    """Parser for CV documents using Ollama LLM"""

    def __init__(self, model: str = OLLAMA_MODEL, max_tokens: int = MAX_TOKENS):
        self.model = model
        self.max_tokens = max_tokens
        self.schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "profile": {
                    "type": "object",
                    "properties": {
                        "basics": {
                            "type": "object",
                            "properties": {
                                "first_name": {"type": "string"},
                                "last_name": {"type": "string"},
                            },
                            "required": ["first_name", "last_name"]
                        },
                    },
                    "required": ["basics"]
                },
                "cv_language": {"type": "string"}
            },
            "required": ["profile"]
        }

        self.prompt_template = """
[SYSTEM] You are an expert system for extracting information following strict JSON format:
- First name and last name (required)
- Email, phone
- Location (city, country)
- Technical skills (simple list)
- Professional experience (position, company, duration)
- Education
- Languages (with level)
- Projects github(name, link, description)
- Certifications(name, organization, date)
- Publications(title, link, date)
- References(name, contact)
- CV language (French, English, etc.)
- Raw CV text (for reference)
- Do not include empty or irrelevant sections

### Details to extract
- Job title
- Companies
- Dates (start and end: month and year)
- Duration (calculated in years and months)
- Indicate if it's an internship
- Identify current company and position if possible
- Calculate total years of experience **excluding internships**
- Diplomas (title, institution, year)
- Languages and level

[CV]
{text}
"""

    def extract_text(self, file_path: str) -> str:
        """Extract text from PDF, DOCX, or TXT files"""
        file_path = Path(file_path)
        ext = file_path.suffix.lower()

        if ext == '.pdf':
            with pdfplumber.open(file_path) as pdf:
                return "\n".join(page.extract_text() or '' for page in pdf.pages)
        elif ext == '.docx':
            doc = Document(file_path)
            return "\n".join(para.text for para in doc.paragraphs)
        elif ext == '.txt':
            return file_path.read_text(encoding='utf-8')
        else:
            raise ValueError(f"Unsupported format: {ext}")

    def truncate_text(self, text: str, max_tokens: int = None) -> str:
        """Truncate text to fit within token limit"""
        if max_tokens is None:
            max_tokens = self.max_tokens
        words = text.split()
        return " ".join(words[:max_tokens])

    def parse_with_ollama(self, text: str) -> Dict[str, Any]:
        """Parse text using Ollama LLM"""
        truncated = self.truncate_text(text)

        response = ollama.generate(
            model=self.model,
            prompt=self.prompt_template.format(text=truncated),
            format="json",
            options={"temperature": 0.1}
        )

        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response['response'], re.DOTALL)
        if not json_match:
            raise ValueError("No JSON found in Ollama response")

        data = json.loads(json_match.group())
        validate(instance=data, schema=self.schema)
        return data

    def parse_cv(self, file_path: str) -> Dict[str, Any]:
        """Parse a single CV file"""
        logger.info(f"Parsing CV: {file_path}")

        text = self.extract_text(file_path)

        # Detect language
        try:
            lang = detect(text) if len(text) > 20 else "fr"
        except:
            lang = "fr"

        data = self.parse_with_ollama(text)
        data["cv_language"] = lang
        data["cv_text"] = text

        return data

    def parse_cv_batch(self, input_dir: str, output_dir: str) -> None:
        """Parse all CVs in a directory"""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        error_log = output_path / "cvparsed.Json"

        files = list(input_path.glob("*.pdf")) + list(input_path.glob("*.docx"))

        for file_path in tqdm(files, desc="Parsing CVs"):
            try:
                data = self.parse_cv(str(file_path))

                output_file = output_path / f"{file_path.stem}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            except Exception as e:
                logger.error(f"Error parsing {file_path}: {e}")
                with open(error_log, "a", encoding='utf-8') as f:
                    f.write(f"{file_path}: {str(e)}\n")

    # === NEW: interactive single-file picker ===
    def parse_cv_interactive(self) -> None:
        """Open a file dialog, parse the chosen CV, save JSON next to it, and print the result."""
        root = tk.Tk()
        root.withdraw()
        file_path = filedialog.askopenfilename(
            title="Choose a CV",
            filetypes=[("Documents", "*.pdf *.docx *.txt")]
        )
        if not file_path:
            print("No file selected.")
            return

        try:
            data = self.parse_cv(file_path)
            out_path = Path(file_path).with_name(Path(file_path).stem + ".json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Print result to console
            print("\n===== PARSED CV RESULT =====\n")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("\nJSON saved to:", str(out_path))

        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            print("\nError during parsing/export:\n", e)

if __name__ == "__main__":
    parser = CVParser()
    # Pick a single file interactively and export JSON next to it
    parser.parse_cv_interactive()

    # (You can still use batch mode if needed)
    # input_dir = r"inputs\CV non technique\Consultant en mobilité internationale"
    # output_dir = r"C:\Users\vali\ATSEY APP\backend\database\ouput_cv"
    # parser.parse_cv_batch(input_dir, output_dir)
