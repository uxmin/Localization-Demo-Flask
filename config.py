import os
from datetime import timedelta
from typing import List


class Config:
    DEBUG: bool = os.environ.get("DEBUG", False)
    # 세션 서명 키. 운영에서는 반드시 환경 변수로 주입한다. (미설정 시 create_app에서 임시 키 생성)
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")

    # 데모 접근 제어용 단일 계정. 자격증명은 코드에 두지 않고 환경 변수로만 주입한다.
    AUTH_USERNAME: str = os.environ.get("AUTH_USERNAME", "")
    AUTH_PASSWORD: str = os.environ.get("AUTH_PASSWORD", "")

    # CORS 허용 origin (쉼표 구분). 미설정 시 동일 출처만 허용한다.
    CORS_ORIGINS: List[str] = [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o]

    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_URL: str = os.environ.get("OPENAI_URL", "")

    PERMANENT_SESSION_LIFETIME: timedelta = timedelta(minutes=30)
    MAX_CONTENT_LENGTH: int = 16 * 1024 * 1024

    SECURITY_KEYWORDS: List[str] = os.environ.get("SECURITY_KEYWORDS", "").split(",")
    GITHUB_TOKEN: str = os.environ.get("GITHUB_TOKEN", "")

    AWS_ACCESS_KEY_ID: str = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_S3_BUCKET_NAME: str = os.environ.get("AWS_S3_BUCKET_NAME", "")

    # Celery Config

    # Celery가 작업 메시지를 보내고 받을 브로커의 URL을 설정합니다. 일반적으로 RabbitMQ, Redis 등을 사용합니다.
    broker_url: str = os.environ.get("CELERY_BROKER_URL")
    # Celery가 작업 결과를 저장할 백엔드를 설정합니다. Redis, 데이터베이스, RPC 등을 사용할 수 있습니다.
    result_backend: str = os.environ.get("CELERY_RESULT_BACKEND")
    broker_connection_retry_on_startup = True

    # 작업 결과의 유효 기간을 설정합니다. 이 시간이 지나면 작업 결과가 자동으로 삭제됩니다. (1시간)
    CELERY_RESULT_EXPIRES = 3600
    # 작업을 직렬화할 때 사용할 포맷을 설정합니다. 기본적으로 JSON, pickle 등을 사용할 수 있습니다.
    CELERY_TASK_SERIALIZER = "json"
    # Celery가 수락할 콘텐츠 유형을 설정합니다. 보안상의 이유로 허용할 콘텐츠 유형을 명시적으로 설정하는 것이 좋습니다.
    CELERY_ACCEPT_CONTENT = ["json"]
    # 작업 결과를 직렬화할 때 사용할 포맷을 설정합니다.
    CELERY_RESULT_SERIALIZER = "json"
    # Celery가 사용할 시간대를 설정합니다.
    CELERY_TIMEZONE = "UTC"
    # UTC 사용 여부를 설정합니다.
    CELERY_ENABLE_UTC = True


class DevelopmentConfig(Config):
    ENV: str = "development"

    DEBUG: bool = True
    PROFILE: bool = True

    result_backend: str = "redis://localhost:6379/0"
    broker_url: str = "redis://localhost:6379/0"
