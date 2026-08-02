import os
import time
import boto3
from botocore.exceptions import ClientError
from werkzeug.utils import secure_filename

# Cloudflare R2 is S3-compatible. This module centralises upload/delete/URL logic
# so blueprints never touch the filesystem or storage details directly.
#
# Required env vars:
#   R2_ACCOUNT_ID              - Cloudflare account id (part of the S3 endpoint)
#   R2_ACCESS_KEY_ID           - R2 API token access key id
#   R2_SECRET_ACCESS_KEY       - R2 API token secret access key
#   R2_BUCKET_NAME             - bucket to store objects in
#   R2_PUBLIC_BASE_URL         - public base url for objects, e.g. https://cdn.example.com
#                                (the custom domain or <bucket>.<account>.r2.dev url)


def _client():
    return boto3.client(
        's3',
        endpoint_url='https://{}.r2.cloudflarestorage.com'.format(os.environ.get('R2_ACCOUNT_ID')),
        aws_access_key_id=os.environ.get('R2_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('R2_SECRET_ACCESS_KEY'),
        region_name='auto',
    )


def _public_base():
    base = os.environ.get('R2_PUBLIC_BASE_URL')
    return base.rstrip('/') if base else ''


def _unique_key(prefix, filename):
    timestamp = int(time.time() * 1000000)
    name = '{}_{}'.format(timestamp, secure_filename(filename))
    return '{}/{}'.format(prefix.strip('/'), name)


def public_url(key):
    base = _public_base()
    if base:
        return '{}/{}'.format(base, key.lstrip('/'))
    return key


def object_key_from_url(url):
    """Derive the object key from a stored url/key.

    Works whether the value is a full public URL or a bare key, and returns
    None for legacy local filesystem paths so they are safely ignored.
    """
    if not url:
        return None
    base = _public_base()
    if base and url.startswith(base):
        return url[len(base):].lstrip('/')
    if url.startswith('http://') or url.startswith('https://'):
        return None
    if os.path.isabs(url):
        return None
    return url


def upload_file(file_storage, prefix):
    """Upload a werkzeug FileStorage to R2 and return its public URL."""
    key = _unique_key(prefix, file_storage.filename)

    try:
        _client().upload_fileobj(
            file_storage.stream,
            os.environ.get('R2_BUCKET_NAME'),
            key,
        )
    except ClientError as e:
        raise Exception('Failed to upload file to storage: {}'.format(e))

    return public_url(key)


def delete_file(url_or_key):
    """Delete an object from R2 given a stored url or key."""
    key = object_key_from_url(url_or_key)

    if not key:
        return

    try:
        _client().delete_object(
            Bucket=os.environ.get('R2_BUCKET_NAME'),
            Key=key,
        )
    except ClientError as e:
        raise Exception('Failed to delete file from storage: {}'.format(e))
