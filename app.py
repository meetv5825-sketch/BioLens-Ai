
import os
import json
import re

from flask import Flask, render_template, request, redirect, session, jsonify
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "biolens-local-secret")

api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key) if api_key else None


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/results")
def results():
    return render_template("results.html")


@app.route("/api/test")
def test_api():
    if not client:
        return jsonify({
            "success": False,
            "message": "Gemini API key .env file mein nahi mili."
        }), 500

    return jsonify({
        "success": True,
        "message": "BioLens AI backend is running!"
    })


@app.route("/analyze", methods=["POST"])
def analyze():
    if not client:
        return jsonify({
            "error": "Gemini API key missing hai. .env file check karo."
        }), 500

    image = request.files.get("profileImage")
    niche = request.form.get("niche", "General Creator")

    if not image or image.filename == "":
        return jsonify({"error": "Please upload a profile image."}), 400

    allowed_types = ["image/jpeg", "image/png", "image/webp"]

    if image.mimetype not in allowed_types:
        return jsonify({
            "error": "Only JPG, PNG and WEBP images are allowed."
        }), 400

    image_bytes = image.read()

    if len(image_bytes) > 10 * 1024 * 1024:
        return jsonify({
            "error": "Image size must be under 10 MB."
        }), 400

    prompt = f"""
You are BioLens AI, an expert Instagram profile and personal branding analyst.

Analyze the uploaded Instagram profile picture for this niche:
{niche}

Return ONLY valid JSON. Do not use markdown or code fences.

Use this exact JSON structure:

{{
  "overall_score": 75,

  "category_scores": {{
    "profile_appeal": 75,
    "niche_match": 75,
    "visual_quality": 75,
    "personal_branding": 75
  }},

  "strengths": [
    "Strength 1",
    "Strength 2",
    "Strength 3"
  ],

  "weaknesses": [
    "Weakness 1",
    "Weakness 2",
    "Weakness 3"
  ],

  "improvements": [
    "Improvement 1",
    "Improvement 2",
    "Improvement 3",
    "Improvement 4"
  ],

  "english": {{
    "summary": "A detailed English summary of the profile picture.",
    "tips": "Give practical tips to improve the profile picture.",
    "profile_photo": "Detailed feedback about the profile photo.",
    "username": "Suggest username improvement ideas based on the niche.",
    "bio": "Explain how the Instagram bio can be improved.",
    "presentation": "Explain how the overall profile presentation can improve."
  }},

  "hindi": {{
    "summary": "Profile picture ka detailed Hindi analysis.",
    "tips": "Profile picture improve karne ke practical tips.",
    "profile_photo": "Profile photo ke baare mein detailed feedback.",
    "username": "Niche ke hisaab se username suggestions.",
    "bio": "Instagram bio improve karne ke suggestions.",
    "presentation": "Overall profile presentation improve karne ke suggestions."
  }},

  "predicted_bios": {{
    "aesthetic": "Line 1\\nLine 2\\nLine 3\\nLine 4",
    "professional": "Line 1\\nLine 2\\nLine 3\\nLine 4",
    "cool": "Line 1\\nLine 2\\nLine 3\\nLine 4"
  }}
}}

IMPORTANT RULES FOR PREDICTED BIOS:

1. Generate THREE different Instagram bios: aesthetic, professional, and cool.
2. EACH bio MUST contain 3 to 4 separate lines.
3. Use the newline character (\\n) between every line.
4. Do NOT put the entire bio in one sentence or one line.
5. Keep every line short, catchy, and Instagram-ready.
6. Use relevant emojis naturally.
7. Make each bio unique and suitable for the user's niche.
8. Do not write placeholders like "Line 1".
9. Do not add numbering such as 1, 2, 3.
10. Return all scores as numbers between 0 and 100.
11. Give honest, constructive feedback. Do not guess sensitive personal information.
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=image.mimetype
                ),
                prompt
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.8
            )
        )

        raw_text = response.text.strip()
        print("GEMINI RESPONSE:", repr(response.text))
print("GEMINI FINISH REASON:", response.candidates[0].finish_reason if response.candidates else "No candidates")
print("GEMINI USAGE:", response.usage_metadata)
        # Remove accidental markdown code fences
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text)
        raw_text = re.sub(r"\s*```$", "", raw_text)

        report = json.loads(raw_text)

        # Ensure all predicted bio styles exist
        predicted_bios = report.get("predicted_bios", {})

        defaults = {
            "aesthetic": "✦ Dream big\n☁ Creating my own vibe\n♡ Living beautifully",
            "professional": "Building my journey\nSharing what I learn\n📩 Let's connect",
            "cool": "⚡ Just getting started\n🔥 Creating my own path\n✨ Stay tuned"
        }

        for style in ["aesthetic", "professional", "cool"]:
            bio = predicted_bios.get(style)

            if not isinstance(bio, str) or not bio.strip():
                predicted_bios[style] = defaults[style]
            else:
                predicted_bios[style] = bio.replace("\\n", "\n").strip()

        report["predicted_bios"] = predicted_bios

        session["report"] = report

        return jsonify({
            "success": True,
            "redirect": "/results"
        })

    except json.JSONDecodeError:
        return jsonify({
            "error": "AI response format issue. Please try again."
        }), 500

    except Exception as e:
        print("Gemini Error:", str(e))
        return jsonify({
            "error": "Analysis failed. Please try again."
        }), 500


if __name__ == "__main__":
    app.run(debug=True)
