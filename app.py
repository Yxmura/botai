import os
import json
import io
import zipfile
from flask import Flask, render_template, request, send_file, jsonify
import google.generativeai as genai
from openai import OpenAI
from dotenv import load_dotenv
from waitress import serve

load_dotenv()

app = Flask(__name__)

GENAI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if GENAI_API_KEY and OPENAI_API_KEY:
    raise ValueError("Use either Gemini / OpenAI API, not both.")

PROVIDER = None
BOT_AVATAR = ""
USER_AVATAR = "/static/avatar/user.png"

if GENAI_API_KEY:
    PROVIDER = "gemini"
    genai.configure(api_key=GENAI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-pro', generation_config={"response_mime_type": "application/json"})
    BOT_AVATAR = "/static/avatar/gemini.png"
elif OPENAI_API_KEY:
    PROVIDER = "openai"
    client = OpenAI(api_key=OPENAI_API_KEY)
    BOT_AVATAR = "/static/avatar/openai.png"

SYSTEM_INSTRUCTION = """
You are a Python Discord Bot generator. 
Generate a fully functional Discord bot based on the user's prompt.
Strict Rules:
1. Bot must be in Python (discord.py or py-cord).
2. All sensitive tokens/variables must be stored in .env.
3. No markdown formatting in the content (plain text code).
4. No comments in any file.
5. It must also keep it so that all commands that will be registered are Guild Commands and that the bot only works in the GUILD_ID in .env
5. Only .py, .db, and .env files are allowed.
6. Output must be a single valid JSON object.
7. The JSON structure must be: {"name": "BotName", "files": [{"filename": "main.py", "content": "..."}, {"filename": ".env", "content": "..."}]}
   The "name" field should be a short, descriptive PascalCase name based on the bot's function (e.g., "ModerationBetter", "Welcomer").
"""

@app.route('/')
def index():
    return render_template('index.html', bot_avatar=BOT_AVATAR, user_avatar=USER_AVATAR)

@app.route('/generate', methods=['POST'])
def generate_bot():
    user_prompt = request.json.get('prompt')
    
    if not user_prompt:
        return jsonify({"error": "No prompt provided"}), 400

    if not PROVIDER:
        return jsonify({"error": "No API key configured"}), 500

    try:
        text_response = ""
        
        if PROVIDER == "gemini":
            full_prompt = f"{SYSTEM_INSTRUCTION}\n\nUser Request: {user_prompt}"
            response = model.generate_content(full_prompt)
            text_response = response.text
        elif PROVIDER == "openai":
            response = client.chat.completions.create(
                model="gpt-5", 
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            text_response = response.choices[0].message.content
        
        try:
            data = json.loads(text_response)
        except json.JSONDecodeError:
            clean_text = text_response.replace('```json', '').replace('```', '')
            data = json.loads(clean_text)

        files = data.get('files', [])
        bot_name = data.get('name', 'discord_bot')
        
        bot_name = "".join(c for c in bot_name if c.isalnum() or c in ('-', '_'))
        if not bot_name: 
            bot_name = "discord_bot"

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_data in files:
                zf.writestr(file_data['filename'], file_data['content'])
        
        memory_file.seek(0)

        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{bot_name}.zip'
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Serving on http://127.0.0.1:5000")
    serve(app, host='127.0.0.1', port=5000)
