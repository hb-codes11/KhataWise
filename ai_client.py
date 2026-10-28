import json
import logging
import re
from typing import Dict, Any, Optional
import requests
import settings

logger = logging.getLogger("ai_client")

def clean_json_text(raw_text: str) -> str:
    """Extract clean JSON substring from model output."""
    raw = raw_text.strip()
    
    # Strip markdown code fence if present
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if code_block_match:
        return code_block_match.group(1).strip()
    
    # Try finding the first '{' and last '}'
    first_brace = raw.find('{')
    last_brace = raw.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return raw[first_brace:last_brace + 1].strip()
        
    return raw

def parse_ai_response(response_text: str) -> Dict[str, str]:
    """
    Parses and validates the AI response JSON packet.
    Guarantees keys 'cmd' and 'mry'.
    """
    cleaned = clean_json_text(response_text)
    try:
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError(f"AI response is not a JSON object: {type(data)}")
        
        cmd = str(data.get("cmd", "")).strip()
        mry = str(data.get("mry", "")).strip()
        
        if not cmd:
            logger.warning("No 'cmd' field in AI response; defaulting to 'quit'")
            cmd = "quit"
            
        return {"cmd": cmd, "mry": mry}
    except Exception as e:
        logger.error(f"Failed to parse AI JSON response: {e}. Raw text was:\n{response_text}")
        # Return fallback packet
        return {
            "cmd": "quit",
            "mry": f"[Parser Fallback] Could not parse valid JSON from AI response: {str(e)}"
        }


class MockAIService:
    """Simulated AI for local testing and self-healing demonstrations."""
    def __init__(self):
        self.step = 0

    def generate(self, prompt: str) -> str:
        self.step += 1
        logger.info(f"[MockAI] Step {self.step} prompt received ({len(prompt)} chars)")
        
        # Step 1: inspect the error log
        if self.step == 1:
            return json.dumps({
                "cmd": "tail -n 10 error.log",
                "mry": "MockAI: Detected new log alerts. Running diagnostic on error.log."
            })
        # Step 2: check processes or touch confirmation
        elif self.step == 2:
            return json.dumps({
                "cmd": "echo 'Self-healing diagnostic executed' >> output.log",
                "mry": "MockAI: Analyzed error. Appended diagnostic confirmation to output.log."
            })
        # Step 3: Finish and quit
        else:
            self.step = 0  # reset for next session
            return json.dumps({
                "cmd": "quit",
                "mry": "MockAI: Self-healing complete. All checks passed and confirmed."
            })


class AIClient:
    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.mock_service = MockAIService()
        self._gemini_client = None

        if self.provider == "gemini":
            try:
                from google import genai
                if settings.GEMINI_API_KEY:
                    self._gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                else:
                    self._gemini_client = genai.Client()
                logger.info(f"Initialized Gemini client with model: {settings.GEMINI_MODEL}")
            except Exception as e:
                logger.warning(f"Could not initialize google-genai ({e}). Will fallback to mock if key missing.")

    def query(self, prompt: str) -> Dict[str, str]:
        """
        Sends the prompt to the configured AI provider and returns {"cmd": ..., "mry": ...}.
        """
        logger.info(f"Querying AI provider '{self.provider}'...")

        if self.provider == "groq" and settings.GROQ_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": settings.GROQ_MODEL,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }
                logger.info(f"Sending prompt to Groq API ({settings.GROQ_MODEL})...")
                resp = requests.post(
                    f"{settings.GROQ_BASE_URL.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                resp.raise_for_status()
                data = resp.json()
                raw_text = data["choices"][0]["message"]["content"]
                return parse_ai_response(raw_text)
            except Exception as e:
                logger.error(f"Groq API query failed: {e}")
                logger.info("Falling back to Mock AI due to Groq API error")
                raw_text = self.mock_service.generate(prompt)
                return parse_ai_response(raw_text)

        elif self.provider == "gemini" and self._gemini_client:
            try:
                response = self._gemini_client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt
                )
                raw_text = response.text or ""
                return parse_ai_response(raw_text)
            except Exception as e:
                logger.error(f"Gemini API query failed: {e}")
                # Fallback to mock if API fails
                logger.info("Falling back to Mock AI due to API error")
                raw_text = self.mock_service.generate(prompt)
                return parse_ai_response(raw_text)

        elif self.provider == "openai_compatible" and settings.OPENAI_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": settings.OPENAI_MODEL,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                }
                url = f"{settings.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
                resp = requests.post(url, headers=headers, json=payload, timeout=45)
                resp.raise_for_status()
                data = resp.json()
                raw_text = data["choices"][0]["message"]["content"]
                return parse_ai_response(raw_text)
            except Exception as e:
                logger.error(f"OpenAI-compatible API query failed: {e}")
                raw_text = self.mock_service.generate(prompt)
                return parse_ai_response(raw_text)

        else:
            # Mock provider or unconfigured key
            raw_text = self.mock_service.generate(prompt)
            return parse_ai_response(raw_text)

