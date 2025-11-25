import os
import pdfplumber
from docx import Document
import re
import json
from jsonschema import validate
import ollama
from tqdm import tqdm
from langdetect import detect
from openai import OpenAI
from sentence_transformers import SentenceTransformer, util
import tkinter as tk
from tkinter import filedialog

# Configuration
OLLAMA_MODEL = "phi3:latest"
MAX_TOKENS = 3000  # Limite plus réaliste

JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "job_profile": {
            "type": "object",
            "properties": {
                "basics": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "company": {"type": "string"}
                    },
                    "required": ["title", "company"]
                }
            },
            "required": ["basics"]
        },
        "jd_language": {"type": "string"},
        "jd_text": {"type": "string"}
    },
    "required": ["job_profile", "jd_language", "jd_text"]
}

PROMPT = '''[SYSTEM] Tu es un assistant d'extraction d'informations pour des offres d'emploi.
Lis le texte fourni et retourne STRICTEMENT un objet JSON avec la structure suivante (aucun champ en plus, aucun champ en moins) 
pour chaque fichier JD. Extrait-moi proprement les sections : profil, missions, compétences, prérequis et formate en JSON standardisé :
{
    "job_profile": {
        "basics": {
            "title": "",
            "company": ""
        }
    },
    "jd_language": "",
    "jd_text": ""
}

RÈGLES :
1. Remplis tous les champs, même vides ("" ou []).
2. Si une information n'est pas présente dans le texte, laisse le champ vide.
3. Ne retourne rien d'autre que l'objet JSON ci-dessus.
4. Ne jamais inventer d'information.

[JOB]
{text}
'''

# --- Extraction du texte à partir d'un fichier ---
def extract_text(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.pdf':
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() or '' for page in pdf.pages)
    elif ext == '.docx':
        doc = Document(file_path)
        return "\n".join(para.text for para in doc.paragraphs)
    elif ext == '.txt':
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        raise ValueError(f"Format non supporté: {ext}")

# --- Troncature du texte ---
def truncate_text(text, max_tokens=3000):
    words = text.split()
    return " ".join(words[:max_tokens])

def parse_with_ollama(text):
    truncated = truncate_text(text, MAX_TOKENS)

    response = ollama.generate(
        model=OLLAMA_MODEL,
        prompt=PROMPT.format(text=truncated),
        options={"temperature": 0.1}
    )

    raw = response["response"]
    match = re.search(r'\{(?:[^{}]|(?R))*\}', raw, re.DOTALL)

    if not match:
        raise ValueError("Impossible d'extraire du JSON depuis Ollama")

    json_str = match.group()

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON mal formé : {e}\nJSON reçu : {json_str}")

    validate(instance=data, schema=JSON_SCHEMA)
    return data


def process_single_file():
    # --- FILE SELECTION DIALOG ---
    root = tk.Tk()
    root.withdraw()

    input_file = filedialog.askopenfilename(
        title="Choose input JD file",
        filetypes=[("Documents", "*.pdf *.docx *.txt")]
    )

    if not input_file:
        print("No file selected.")
        return

    # Output directory = same directory as input file
    output_dir = os.path.dirname(input_file)
    os.makedirs(output_dir, exist_ok=True)

    try:
        text = extract_text(input_file)
        lang = detect(text) if len(text) > 20 else "fr"

        data = parse_with_ollama(text)

        # Add language + full text
        data["jd_language"] = lang
        data["jd_text"] = text

        output_path = os.path.join(
            output_dir,
            f"{os.path.splitext(os.path.basename(input_file))[0]}.json"
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # --- PRINT RESULT ON CONSOLE ---
        print("\n===== PARSED RESULT =====\n")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("\nJSON saved to:", output_path)

    except Exception as e:
        print("Error:", e)


if __name__ == "__main__":
    process_single_file()
