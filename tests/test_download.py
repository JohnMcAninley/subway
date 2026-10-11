"""Downloading the static GTFS, and recovering when that goes wrong, against a fake of the MTA's server."""
import io
import zipfile

import pytest
import requests

from subway_clock.core import gtfs
from subway_clock.core.gtfs import StaticData, update

URL = "https://example.invalid/gtfs.zip"

FILES = {
    "stops.txt": "stop_id,stop_name,parent_station\n633,28 St,\n633S,28 St,633\n",
    "trips.txt": "route_id,trip_id,trip_headsign\n6,WKD_000600_6..S01R,Brooklyn Bridge-City Hall\n",
    "stop_times.txt": "trip_id,stop_id\nWKD_000600_6..S01R,633S\n",
}


def gtfs_zip(files=FILES):
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return content.getvalue()


class Response:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content
        self.headers = {"Content-Length": str(len(content)), "Last-Modified": "Sat, 10 Oct 2026 12:00:00 GMT"}

    def iter_content(self, chunk_size):
        return (self.content[i:i + chunk_size] for i in range(0, len(self.content), chunk_size))

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} from the fake server")


@pytest.fixture
def server(monkeypatch):
    """Answers each download with the next of server.responses (the last one from then on).

    A response is zip content, an HTTP status, or an exception to raise; a
    request for a copy the client already has gets a 304. server.requests
    counts the requests.
    """
    class Server:
        responses = [gtfs_zip()]
        requests = 0

    def get(url, headers, **kwargs):
        response = Server.responses[min(Server.requests, len(Server.responses) - 1)]
        Server.requests += 1
        if isinstance(response, Exception):
            raise response
        if isinstance(response, int):
            return Response(response)
        return Response(304) if "If-Modified-Since" in headers else Response(200, response)

    monkeypatch.setattr(gtfs.requests, "get", get)
    return Server


def test_update_downloads_and_extracts_once(tmp_path, server):
    assert update(URL, tmp_path, "gtfs") is True
    assert (tmp_path / "gtfs" / "stops.txt").read_text() == FILES["stops.txt"]

    assert update(URL, tmp_path, "gtfs") is False  # 304: nothing new
    assert not (tmp_path / "gtfs.part").exists()


def test_update_replaces_what_was_extracted_before(tmp_path, server):
    (tmp_path / "gtfs").mkdir()
    (tmp_path / "gtfs" / "old.txt").write_text("from an older zip")

    assert update(URL, tmp_path, "gtfs") is True
    assert not (tmp_path / "gtfs" / "old.txt").exists()


def test_bad_zip_is_downloaded_again(tmp_path, server):
    server.responses = [b"<html>not a zip</html>", gtfs_zip()]

    assert update(URL, tmp_path, "gtfs") is False
    assert not (tmp_path / "gtfs.zip").exists()  # so the next request isn't answered "not modified"
    assert update(URL, tmp_path, "gtfs") is True
    assert (tmp_path / "gtfs" / "stops.txt").exists()


def test_zip_with_a_damaged_file_is_downloaded_again(tmp_path, server):
    damaged = bytearray(gtfs_zip())
    at = damaged.index(b"633S")  # stored uncompressed, so this breaks its checksum
    damaged[at:at + 4] = b"XXXX"
    server.responses = [bytes(damaged), gtfs_zip()]

    assert update(URL, tmp_path, "gtfs") is False
    assert not (tmp_path / "gtfs").exists()
    assert update(URL, tmp_path, "gtfs") is True


def test_interrupted_extraction_is_redone(tmp_path, server):
    update(URL, tmp_path, "gtfs")
    # As if the power went while it was extracting: some files, and no marker.
    (tmp_path / "gtfs" / gtfs.EXTRACTED_MARKER).unlink()
    (tmp_path / "gtfs" / "stop_times.txt").unlink()

    assert update(URL, tmp_path, "gtfs") is True  # though the server said 304
    assert (tmp_path / "gtfs" / "stop_times.txt").exists()


def test_failed_download_raises_and_keeps_the_old_copy(tmp_path, server):
    update(URL, tmp_path, "gtfs")
    for failure in (500, requests.ConnectionError("no network")):
        server.responses = [failure]
        server.requests = 0
        with pytest.raises(requests.RequestException):
            update(URL, tmp_path, "gtfs")
    assert (tmp_path / "gtfs" / "stops.txt").exists()


def test_first_run_prepares_with_progress(tmp_path, server):
    static = StaticData(tmp_path)
    assert not static.ready
    assert static.routes_for(["633S"]) == []

    reports = []
    static.prepare(lambda stage, fraction: reports.append((stage, fraction)))

    assert static.ready
    assert static.routes_for(["633S"]) == ["6"]
    assert static.headsigns == {"000600_6..S01R": "Brooklyn Bridge-City Hall"}
    stages = list(dict.fromkeys(stage for stage, _ in reports))
    assert stages == ["Downloading schedules", "Unpacking schedules", "Reading schedules"]
    fractions = [fraction for _, fraction in reports]
    assert fractions == sorted(fractions) and 0 < fractions[0] and fractions[-1] <= 1

    assert StaticData(tmp_path).ready  # the next run starts from the cached copy


def test_first_run_with_no_network_can_be_tried_again(tmp_path, server):
    server.responses = [requests.ConnectionError("no network"), gtfs_zip()]
    static = StaticData(tmp_path)

    with pytest.raises(requests.ConnectionError):
        static.prepare()
    assert not static.ready

    static.prepare()
    assert static.ready


def test_first_run_with_a_bad_download_can_be_tried_again(tmp_path, server):
    server.responses = [b"not a zip", gtfs_zip()]
    static = StaticData(tmp_path)

    with pytest.raises(StaticData.LOAD_ERRORS):
        static.prepare()
    assert not static.ready

    static.prepare()
    assert static.ready


def test_downloaded_but_not_indexed_prepares_without_a_network(tmp_path, server):
    StaticData(tmp_path).prepare()
    (tmp_path / "stop_routes.json").write_text("{cut short")
    server.responses = [requests.ConnectionError("no network")]

    static = StaticData(tmp_path)
    assert not static.ready  # indexing takes too long to do before there is a window
    static.prepare()
    assert static.routes_for(["633S"]) == ["6"]
