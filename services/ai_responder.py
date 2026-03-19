import os
import logging
import requests

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GEMINI_URL = (
    'https://generativelanguage.googleapis.com/v1beta/models/'
    'gemini-1.5-flash:generateContent'
)

TONE_INSTRUCTIONS = {
    'professional': 'Be professional, courteous, and composed. Use proper grammar.',
    'friendly': 'Be warm, upbeat, and conversational — like a friend who also runs a great business.',
    'formal': 'Be formal and polished. Use complete sentences and a respectful tone.',
}

NEGATIVE_EXTRA = (
    'The reviewer left a negative or low rating. Acknowledge their concern with empathy, '
    'apologize if appropriate, and offer to make it right. Include an invitation to contact '
    'the business directly (e.g., "please call us at [phone] or email [email]"). '
    'Do NOT be defensive.'
)

POSITIVE_EXTRA = (
    'The reviewer left a positive or 5-star review. Express genuine gratitude. '
    'If they mentioned a specific service, technician, or detail, reference it briefly. '
    'End with a warm closing.'
)


def generate_response(
    business_name: str,
    business_type: str,
    reviewer_name: str,
    star_rating: int,
    review_text: str,
    tone: str = 'professional',
) -> str:
    """
    Generate a personalized Google review response using Gemini REST API.

    Returns the response text, or raises an exception on failure.
    """
    tone_instruction = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS['professional'])
    sentiment_instruction = POSITIVE_EXTRA if star_rating >= 4 else NEGATIVE_EXTRA

    if review_text:
        prompt = (
            f"You are the owner of {business_name}, a {business_type} company. "
            f"You are responding to a Google Business review. "
            f"{tone_instruction} "
            "Write a genuine, personalized response — never robotic or templated. "
            "Keep it 2-4 sentences maximum. "
            "Do NOT include a subject line, greeting like 'Dear', or sign-off like 'Sincerely'. "
            "Just the response body.\n\n"
            f"Reviewer name: {reviewer_name}\n"
            f"Star rating: {star_rating}/5\n"
            f"Review text: \"{review_text}\"\n\n"
            f"{sentiment_instruction}\n"
            "Write the response now:"
        )
    else:
        prompt = (
            f"You are the owner of {business_name}, a {business_type} company. "
            f"You are responding to a Google Business review. "
            f"{tone_instruction} "
            "Write a genuine, personalized response — never robotic or templated. "
            "Keep it 2-4 sentences maximum. "
            "Do NOT include a subject line, greeting like 'Dear', or sign-off like 'Sincerely'. "
            "Just the response body.\n\n"
            f"Reviewer name: {reviewer_name}\n"
            f"Star rating: {star_rating}/5 (no written comment)\n\n"
            f"{sentiment_instruction}\n"
            "Write the response now:"
        )

    payload = {
        'contents': [{'parts': [{'text': prompt}]}],
        'generationConfig': {
            'maxOutputTokens': 200,
            'temperature': 0.8,
        },
    }

    try:
        resp = requests.post(
            GEMINI_URL,
            params={'key': GEMINI_API_KEY},
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data['candidates'][0]['content']['parts'][0]['text'].strip()
        logger.info(f'Generated response for {reviewer_name} ({star_rating}★) at {business_name}')
        return text

    except Exception as e:
        logger.error(f'Gemini API error generating response: {e}')
        raise
