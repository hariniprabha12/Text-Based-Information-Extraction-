import os
from flask import Flask, request, render_template, send_file
import re
from PyPDF2 import PdfReader
import pandas as pd
from groq import Groq

# Initialize Flask app and Groq API client
app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "output"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["OUTPUT_FOLDER"] = OUTPUT_FOLDER
client = Groq(api_key="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")

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Function to extract text from a specific page of the PDF
def extract_pdf_text_by_page(pdf_path, page_number):
    reader = PdfReader(pdf_path)
    page_text = reader.pages[page_number].extract_text() if page_number < len(reader.pages) else ""
    return page_text

# Function to send text to Groq's LLM and request extraction of titles and procedures
def extract_multiple_experiments_with_groq(page_text):
    messages = [
        {
            "role": "user",
            "content": (
                "You are a text extraction tool. Identify and extract each experiment's title and the corresponding 'Procedure' "
                "or 'Comments' section separately from the provided text. Each experiment starts with a numbered title line, "
                "followed by 'IDENTIFICATION:' and 'COMMENTS', and may contain multiple lines.\n\n"
                "If 'Procedure' is missing, use 'Comments' as 'Procedure'. Format each extraction as follows:\n\n"
                "**Experiment Title:** [Extracted Title]\n\n**Procedure:** [Extracted Procedure (or Comments if Procedure is missing)]\n\n"
                "Here is the page content:\n\n" + page_text
            )
        }
    ]

    # Request completion from Groq's LLM
    chat_completion = client.chat.completions.create(
        messages=messages,
        model="llama3-8b-8192",
    )
    extracted_text = chat_completion.choices[0].message.content
    return extracted_text

# Process and structure the extracted experiments for DataFrame storage
def process_extracted_experiments(extracted_text):
    experiment_pattern = r'\*\*Experiment Title:\*\* (.+?)\n\n\*\*Procedure:\*\*([\s\S]+?)(?=\n\n\*\*Experiment Title|\Z)'
    matches = re.findall(experiment_pattern, extracted_text, re.DOTALL)
    experiments = [(title.strip(), procedure.strip()) for title, procedure in matches]
    return experiments

# Extract experiments from all pages
def extract_experiments_from_all_pages(pdf_file_path):
    all_experiments = []
    reader = PdfReader(pdf_file_path)
    total_pages = len(reader.pages)

    for page_number in range(total_pages):
        page_text = extract_pdf_text_by_page(pdf_file_path, page_number)
        if page_text.strip():
            extracted_text = extract_multiple_experiments_with_groq(page_text)
            experiments = process_extracted_experiments(extracted_text)
            all_experiments.extend(experiments)

    df = pd.DataFrame(all_experiments, columns=['Title', 'Procedure'])
    df["Class"] = "XII"
    df["Subject"] = "Zoology"
    df["List Of Experiment"] = [f"{i}" for i in range(1, len(df) + 1)]
    df = df[["Class", "Subject", "List Of Experiment", "Title", "Procedure"]]
    output_excel_path = os.path.join(app.config["OUTPUT_FOLDER"], "Extracted_Experiments_All_Pages.xlsx")
    df.to_excel(output_excel_path, index=False)

    return all_experiments, output_excel_path

# Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "pdf_file" not in request.files:
        return "No file uploaded", 400

    file = request.files["pdf_file"]
    if file.filename == "":
        return "No selected file", 400

    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)

    # Process the uploaded PDF
    all_experiments, output_excel_path = extract_experiments_from_all_pages(file_path)

    # Render extracted data for each experiment
    experiment_details = [
        {"index": i, "title": title, "procedure": procedure}
        for i, (title, procedure) in enumerate(all_experiments, start=1)
    ]

    return render_template(
        "results.html",
        experiments=experiment_details,
        download_link=output_excel_path,
    )

@app.route("/download")
def download_file():
    file_path = os.path.join(app.config["OUTPUT_FOLDER"], "Extracted_Experiments_All_Pages.xlsx")
    return send_file(file_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
