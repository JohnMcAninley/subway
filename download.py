import os
import requests
import zipfile
from datetime import datetime
from email.utils import parsedate_to_datetime

def download_if_newer_zip(url, local_zip_path):
    headers = {}

    if os.path.exists(local_zip_path):
        local_mtime = datetime.utcfromtimestamp(os.path.getmtime(local_zip_path))
        headers['If-Modified-Since'] = local_mtime.strftime('%a, %d %b %Y %H:%M:%S GMT')

    response = requests.get(url, headers=headers, stream=True)

    if response.status_code == 304:
        print("ZIP file is up to date. No download needed.")
        return False
    elif response.status_code == 200:
        with open(local_zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Update mtime based on Last-Modified header if present
        last_modified = response.headers.get('Last-Modified')
        if last_modified:
            remote_mtime = parsedate_to_datetime(last_modified).timestamp()
            os.utime(local_zip_path, (remote_mtime, remote_mtime))

        print("Downloaded updated ZIP file.")
        return True
    else:
        print(f"Failed to download ZIP. Status code: {response.status_code}")
        return False


def unzip_and_replace(zip_path, extract_to):
    if not zipfile.is_zipfile(zip_path):
        print("Provided file is not a valid ZIP archive.")
        return False

    print(f"Extracting ZIP to: {extract_to}")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)
    return True


if __name__ == "__main__":
    if download_if_newer_zip("https://rrgtfsfeeds.s3.amazonaws.com/gtfs_supplemented.zip", "gtfs_supplemented.zip"):
        unzip_and_replace("gtfs_supplemented.zip", "gtfs-supplemented")
