import json
import os
import re
from io import BytesIO
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory


ROOT_DIR = Path(__file__).resolve().parent.parent
FRONT_DIR = ROOT_DIR / "front"
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
MAX_FILE_SIZE = 5 * 1024 * 1024

app = Flask(__name__, static_folder=str(FRONT_DIR), static_url_path="")
load_dotenv(ROOT_DIR / ".env")


def extract_resume_text(file_storage):
    """Extract text locally so the agent receives only the resume content."""
    filename = Path(file_storage.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Please upload a PDF, DOC, or DOCX resume.")

    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError("The uploaded resume is empty.")
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError("The resume must be smaller than 5 MB.")

    if extension == ".pdf":
        from pypdf import PdfReader

        pages = PdfReader(BytesIO(file_bytes)).pages
        return "\n".join(page.extract_text() or "" for page in pages).strip()

    if extension == ".docx":
        from docx import Document

        document = Document(BytesIO(file_bytes))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()

    raise ValueError("Legacy .doc files are not supported. Save it as .docx or PDF and try again.")


def get_agent_response(resume_text, job_description):
    project_endpoint = os.environ.get("PROJECT_ENDPOINT")
    agent_name = os.environ.get("AGENT_NAME", "resume-scanner-agent")
    if not project_endpoint:
        raise RuntimeError("Azure is not configured. Set PROJECT_ENDPOINT in the .env file.")

    project_client = AIProjectClient(
        credential=DefaultAzureCredential(),
        endpoint=project_endpoint,
    )
    openai_client = project_client.get_openai_client()
    agent = project_client.agents.get(agent_name=agent_name)
    conversation = openai_client.conversations.create(items=[])

    prompt = f"""
Analyze this resume against the job description. Return ONLY valid JSON, with no markdown fences.
Use this exact schema:
{{
  "score": 0,
  "message": "short overall assessment",
  "matched_skills": ["skill"],
  "missing_skills": ["skill"],
  "improvements": ["specific recommendation"],
  "breakdown": {{"Technical Skills": 0, "Experience": 0, "Education": 0, "Projects": 0}}
}}
Scores must be integers from 0 to 100. Keep each list concise and ground every observation in the supplied text.

RESUME:
{resume_text[:30000]}

JOB DESCRIPTION:
{job_description[:20000]}
"""
    openai_client.conversations.items.create(
        conversation_id=conversation.id,
        items=[{"type": "message", "role": "user", "content": prompt}],
    )
    response = openai_client.responses.create(
        conversation=conversation.id,
        extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
        input="",
    )
    content = getattr(response, "output_text", "") or ""
    if not content:
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", "") != "message":
                continue
            for content_item in getattr(item, "content", []) or []:
                if getattr(content_item, "type", "") == "output_text":
                    content = getattr(content_item, "text", "")
                    break

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise RuntimeError("The Azure agent returned an unreadable analysis.")
    result = json.loads(match.group(0))
    result["score"] = max(0, min(100, int(result.get("score", 0))))
    result.setdefault("matched_skills", [])
    result.setdefault("missing_skills", [])
    result.setdefault("improvements", [])
    result.setdefault("breakdown", {})
    return result


@app.get("/")
def index():
    return send_from_directory(FRONT_DIR, "index.html")


@app.post("/api/analyze")
def analyze():
    try:
        resume = request.files.get("resume")
        job_description = request.form.get("job_description", "").strip()
        if resume is None:
            return jsonify(error="Please upload a resume."), 400
        if len(job_description) < 50:
            return jsonify(error="Please enter a complete job description."), 400
        resume_text = extract_resume_text(resume)
        if len(resume_text) < 30:
            return jsonify(error="Could not extract enough text from this resume."), 400
        return jsonify(get_agent_response(resume_text, job_description))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    except Exception as error:
        app.logger.exception("Resume analysis failed")
        return jsonify(error=f"Analysis failed: {error}"), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8000")), debug=True)