import uuid

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import current_app

from app.utils.external_files import extract_and_validate_mime, get_extension_from_mime


class S3Helper:
    def __init__(self, region_name: str = "ap-northeast-2"):
        self.region_name = region_name
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=current_app.config.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=current_app.config.get("AWS_SECRET_ACCESS_KEY"),
            region_name=self.region_name,
        )

    def upload_file(
        self,
        bucket_name: str,
        file_content: bytes,
        content_type: str | None = None,
        file_name: str | None = None,
        upload_path: list[str] = [],
    ) -> str | None:
        try:
            _path = "/".join(upload_path)
            content_type = content_type or extract_and_validate_mime(file_content)
            if not content_type:
                return None

            _ext = get_extension_from_mime(content_type)
            _file_name = file_name or str(uuid.uuid4())
            filename = f"{_file_name}{_ext}" if _ext else _file_name

            _key = f"{_path}/{filename}".lstrip("/")

            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=_key,
                Body=file_content,
                ContentType=content_type,
            )

            return f"https://{bucket_name}.s3.{self.region_name}.amazonaws.com/{_key}"
        except (BotoCoreError, ClientError) as e:
            current_app.logger.error(e, exc_info=True)
            return None

    def delete_file(self, bucket_name: str, file_url: str) -> bool:
        try:

            _key = file_url.replace(f"https://{bucket_name}.s3.{self.region_name}.amazonaws.com/", "")
            self.s3_client.delete_object(Bucket=bucket_name, Key=_key)
            return True
        except (BotoCoreError, ClientError) as e:
            current_app.logger.error(e, exc_info=True)
            return False

    def delete_folder(self, bucket_name: str, folder_prefix: str):
        """
        S3 버킷의 특정 폴더(접두사)에 있는 모든 객체를 삭제합니다.

        Args:
            bucket_name (str): S3 버킷 이름
            folder_prefix (str): 삭제할 폴더의 접두사 (예: "my_work_folder")
        """
        # 접두사가 비어있거나 루트 디렉토리인 경우의 실수를 방지합니다.
        if not folder_prefix:
            current_app.logger.error("폴더 접두사가 비어 있어 삭제 작업을 중단합니다.")
            return

        # S3에서는 폴더를 구분하기 위해 접두사 끝에 '/'를 붙이는 것이 일반적입니다.
        prefix = folder_prefix.strip("/") + "/"

        current_app.logger.info(f"S3 버킷 '{bucket_name}'에서 '{prefix}' 접두사를 가진 객체 삭제를 시작합니다.")

        try:
            # 1. 삭제할 객체 목록 가져오기 (1000개 이상도 처리 가능하도록 Paginator 사용)
            paginator = self.s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

            objects_to_delete = []
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        objects_to_delete.append({"Key": obj["Key"]})

            # 2. 삭제할 객체가 없으면 함수 종료
            if not objects_to_delete:
                current_app.logger.info(f"'{prefix}' 접두사에 삭제할 객체가 없습니다.")
                return

            current_app.logger.info(f"총 {len(objects_to_delete)}개의 객체를 삭제합니다.")

            # 3. 객체 삭제 (delete_objects는 한 번에 최대 1000개까지 가능)
            # 1000개씩 나눠서 삭제 요청을 보냅니다.
            for i in range(0, len(objects_to_delete), 1000):
                chunk = objects_to_delete[i : i + 1000]
                self.s3_client.delete_objects(Bucket=bucket_name, Delete={"Objects": chunk})
                current_app.logger.info(f"{len(chunk)}개의 객체 묶음 삭제 완료.")

        except ClientError as e:
            current_app.logger.error(f"S3 폴더 삭제 중 오류 발생: {e}")
            # 필요에 따라 예외를 다시 발생시키거나 처리할 수 있습니다.
            raise
