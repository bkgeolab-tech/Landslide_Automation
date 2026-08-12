import os
import mimetypes
from pathlib import Path
import boto3
from botocore.exceptions import NoCredentialsError, ClientError

# Lấy cấu hình S3 từ biến môi trường
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://sgp1.digitaloceanspaces.com")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")
S3_PUBLIC_DOMAIN = os.getenv("S3_PUBLIC_DOMAIN", "") # e.g. https://your-bucket.sgp1.cdn.digitaloceanspaces.com

# Kiểm tra xem tính năng S3 có được bật không
def is_s3_enabled() -> bool:
    return bool(S3_BUCKET_NAME and S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY)

# Khởi tạo S3 Client
def get_s3_client():
    if not is_s3_enabled():
        return None
    return boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT_URL,
        aws_access_key_id=S3_ACCESS_KEY_ID,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY
    )

def upload_file_to_s3(local_path: Path, s3_key: str, content_type: str = None) -> bool:
    """Đẩy file lên S3 và trả về True nếu thành công."""
    client = get_s3_client()
    if not client:
        return False
        
    if not content_type:
        content_type, _ = mimetypes.guess_type(str(local_path))
        if not content_type:
            content_type = "application/octet-stream"

    try:
        client.upload_file(
            Filename=str(local_path),
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            ExtraArgs={
                'ACL': 'public-read',
                'ContentType': content_type
            }
        )
        return True
    except (NoCredentialsError, ClientError) as e:
        print(f"Lỗi khi upload lên S3: {e}")
        return False

def get_public_url(s3_key: str) -> str:
    """Lấy link truy cập công khai của file trên mây."""
    if S3_PUBLIC_DOMAIN:
        # Dùng tên miền CDN tuỳ chỉnh nếu có
        domain = S3_PUBLIC_DOMAIN.rstrip('/')
        return f"{domain}/{s3_key}"
    
    # Dùng URL mặc định của DigitalOcean / S3
    endpoint = S3_ENDPOINT_URL.rstrip('/')
    return f"{endpoint}/{S3_BUCKET_NAME}/{s3_key}"
