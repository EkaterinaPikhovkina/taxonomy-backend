import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables.")
    raise ValueError("GEMINI_API_KEY not found. Please set it in a .env file or environment.")

genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-04-17")


async def generate_taxonomy_with_llm(corpus_text: str) -> str:
    model = genai.GenerativeModel(MODEL_NAME)
    logger.info(f"Using Gemini model: {MODEL_NAME}")

    prompt = f"""
Ти – експерт з онтологій та обробки природної мови. Твоє завдання – проаналізувати наданий корпус текстів українською мовою та створити з нього ієрархічну таксономію.
Таксономія має бути представлена у форматі Turtle (TTL).

Вимоги до таксономії:
1.  **Формат:** Строго Turtle (TTL).
2.  **Префікси:** Використовуй наступні префікси:
    ```ttl
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    @prefix ex: <http://example.org/taxonomy/document-corpus/> .
    ```
3.  **Структура:**
    *   Кожен концепт має бути екземпляром `rdfs:Class`.
    *   Використовуй `rdfs:subClassOf` для визначення ієрархії.
    *   Кожен концепт повинен мати `rdfs:label` українською (`@uk`) та англійською (`@en`) мовами. Якщо англійський відповідник не очевидний, надай адекватний переклад або транслітерацію.
    *   Кожен концепт повинен мати `rdfs:comment` українською (`@uk`) та англійською (`@en`) мовами, що коротко описує концепт.
4.  **Ієрархія:** Створи логічну ієрархію концептів (2-4 рівні глибини), виявлених у тексті. Мають бути як загальні (верхньорівневі) концепти, так і більш специфічні підкласи.
6.  **Якість:** Намагайся ідентифікувати ключові сутності, поняття, процеси, ролі тощо, описані в тексті. Уникай надто загальних або надто специфічних (одиничних) концептів, якщо вони не утворюють ієрархію.
7.  **Тільки TTL:** Твоя відповідь повинна містити ТІЛЬКИ TTL дані, без жодних пояснень, коментарів Markdown чи інших текстів до або після TTL блоку. Почни відповідь безпосередньо з `@prefix`.

Приклад структури для одного концепту:
```ttl
ex:SomeConceptName
    a rdfs:Class ;
    rdfs:subClassOf ex:SomeParentConcept ; # (якщо це не топ-рівневий концепт)
    rdfs:label "Назва концепту"@uk ;
    rdfs:label "Concept Name"@en ;
    rdfs:comment "Короткий опис концепту українською."@uk ;
    rdfs:comment "Short description of the concept in English."@en .
    
    Наданий корпус текстів:
    --- START OF CORPUS ---
{corpus_text}
--- END OF CORPUS ---

Твоя відповідь (тільки TTL):
    """

    logger.info(f"Sending prompt to Gemini. Corpus length: {len(corpus_text)} chars.")

    try:
        MAX_OUTPUT_TOKENS = os.getenv("MAX_OUTPUT_TOKENS", 65500)

        generation_config = genai.types.GenerationConfig(
            # temperature=0.7,
            # max_output_tokens=int(MAX_OUTPUT_TOKENS)
        )
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        if response.parts:
            full_response_text = response.text.strip()
            logger.debug(f"Raw LLM response (full): \n{full_response_text}")
            ttl_data = full_response_text

            if len(response.text) >= int(MAX_OUTPUT_TOKENS):
                logger.warning(f"LLM response might have been truncated by max_output_tokens ({MAX_OUTPUT_TOKENS}).")

            if not ttl_data.startswith("@prefix"):
                logger.warning("LLM response did not start with @prefix. Attempting to clean.")

                ttl_start_index = ttl_data.find("@prefix")
                if ttl_start_index == -1:
                    logger.error(
                        f"LLM response did not contain @prefix. Cannot extract TTL. Response starts with: {ttl_data[:500]}")
                    raise ValueError("ЛЛМ повернула відповідь у неочікуваному форматі (відсутній @prefix).")

                ttl_data = ttl_data[ttl_start_index:]

                ttl_end_index_markdown = ttl_data.find("\n```")
                if ttl_end_index_markdown != -1:
                    logger.warning(
                        f"Found potential markdown end at index {ttl_end_index_markdown}. Truncating response.")
                    ttl_data = ttl_data[:ttl_end_index_markdown]

                if not ttl_data.strip():
                    logger.error("Extracted TTL data is empty after cleaning.")
                    raise ValueError("Не вдалося витягти валідні TTL дані з відповіді ЛЛМ.")

            logger.info(f"LLM generated taxonomy: {ttl_data}")
            return ttl_data
        else:
            logger.error(f"LLM response was empty or blocked. Feedback: {response.prompt_feedback}")
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else "Unknown"
            block_message = f"ЛЛМ не повернула контент або запит було заблоковано. Причина: {block_reason}"
            if response.prompt_feedback and response.prompt_feedback.safety_ratings:
                block_message += f" Safety Ratings: {response.prompt_feedback.safety_ratings}"
            raise ValueError(block_message)

    except Exception as e:
        logger.exception(f"Error calling Gemini API: {e}")
        raise
