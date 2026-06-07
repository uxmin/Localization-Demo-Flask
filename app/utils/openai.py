import os
from typing import Tuple, TypeVar

from flask import current_app
from google import genai
from google.genai import types
from langchain.output_parsers.json import SimpleJsonOutputParser
from langchain.schema import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_openai import ChatOpenAI

from app.exceptions import PromptNotFoundError
from app.utils.etc import clean_response

PARSER = TypeVar("PARSER")


def get_template(prompt_name: str) -> ChatPromptTemplate:
    """프롬프트 템플릿을 로드한다. 파일이 없으면 PromptNotFoundError를 발생시킨다."""
    prompt_path = os.path.join(current_app.root_path, "data", "prompts", f"{prompt_name}.txt")

    try:
        with open(prompt_path, "r") as prompt_file:
            system_prompt = prompt_file.read().strip()
    except FileNotFoundError as e:
        raise PromptNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {prompt_name}") from e

    system_message = SystemMessagePromptTemplate.from_template(system_prompt)
    human_message = HumanMessagePromptTemplate.from_template("{user_input}")
    prompt_template = ChatPromptTemplate.from_messages([system_message, human_message])

    return prompt_template


def get_model(
    model: str = "gpt-4o-mini", temperature: float = 0.4, max_tokens: int = 5000, is_json: bool = False
) -> Tuple[ChatOpenAI, PARSER]:
    if is_json:
        response_format = {"response_format": {"type": "json_object"}}
        parser = SimpleJsonOutputParser()
    else:
        response_format = {"response_format": {"type": "text"}}
        parser = StrOutputParser()

    return (
        ChatOpenAI(model=model, temperature=temperature, max_tokens=max_tokens, model_kwargs=response_format),
        parser,
    )


def get_model_list():
    """플레이그라운드에서 선택 가능한 모델 목록을 반환한다(정적 목록)."""
    models = []

    gpt_models = [
        "gpt-4.1-2025-04-14",
        "gpt-4.1-mini-2025-04-14",
        "gpt-4.1-nano-2025-04-14",
        "gpt-4o-2024-11-20",
        "gpt-4o-2024-08-06",
        "gpt-4o-2024-05-13",
        "gpt-4o-mini-2024-07-18",
        "o4-mini-2025-04-16",
        "o3-mini-2025-01-31",
        "o1-mini-2024-09-12",
        "gpt-4o-mini-search-preview-2025-03-11",
        "gpt-4o-search-preview-2025-03-11",
        "chatgpt-4o-latest",
        "gpt-3.5-turbo-0125",
        "gpt-3.5-turbo-1106",
        "gpt-3.5-turbo-0613",
        "gpt-3.5-0301",
        "gpt-3.5-turbo-instruct",
        "gpt-3.5-turbo-16k-0613",
    ]
    models.extend(gpt_models)

    gen_models = [
        "gemini-2.5-flash-preview-04-17",
        "gemini-2.5-pro-preview-05-06",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro",
    ]
    models.extend(gen_models)

    return models


def call_model(api_key: str, model_name: str, prompt: str, user_input: str) -> str:
    try:
        if model_name.startswith("gpt"):
            llm = ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                temperature=1,
            )
            messages = [SystemMessage(content=prompt), HumanMessage(content=user_input)]
            response = llm.invoke(messages)
            content = response.content.strip()
        elif model_name.startswith("gemini"):
            gclient = genai.Client(api_key=api_key)
            response = gclient.models.generate_content(
                model=model_name,
                config=types.GenerateContentConfig(system_instruction=prompt),
                contents=[user_input],
            )
            content = response.text.strip()
        else:
            raise ValueError("Unsupported Model")

        if not content:
            raise ValueError("Empty")
        return clean_response(content)
    except Exception as e:
        current_app.logger.error(f"모델 호출 실패: {e}")
        if "authentication" in str(e).lower() or "api key" in str(e).lower():
            raise ValueError("INVALID API KEY")
        raise Exception(f"Error during model call:\n{e}")
