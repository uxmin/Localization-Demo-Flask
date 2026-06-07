import mimetypes

import magic


def extract_and_validate_mime(file_content: bytes, allowed_types: list[str] = None) -> str | None:
    mime = magic.Magic(mime=True)
    content_type = mime.from_buffer(file_content)
    if allowed_types and content_type not in allowed_types:
        return None
    return content_type


def get_extension_from_mime(content_type: str) -> str | None:
    ext = mimetypes.guess_extension(content_type)
    if ext is None:
        return None
    return ext
