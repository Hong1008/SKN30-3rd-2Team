"""RunPod Pod용 HTTP 서버.

POST /runsync의 요청·응답 외피를 RunPod Serverless와 호환시켜 기존
ApiEmbedder·ApiReranker가 Pod URL로 전환돼도 같은 payload를 사용할 수 있게 한다.
"""

from __future__ import annotations

import json
import os
import hmac
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from service import handle_input


class PodRequestHandler(BaseHTTPRequestHandler):
    """공개 /runsync 요청을 공용 서비스 라우터에 전달한다."""

    server_version = "WorkShieldEmbeddingPod/1.0"

    def _write_json(self, status: HTTPStatus, body: dict[str, Any]) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _authorized(self) -> bool:
        """Pod proxy 공개 포트에서 worker 전용 API key를 검증한다."""
        expected = os.getenv("EMBED_API_KEY")
        if not expected:
            # key 없이 기동한 이미지는 운영 readiness를 통과할 수 없게 한다.
            return False
        received = self.headers.get("Authorization", "")
        return hmac.compare_digest(received, f"Bearer {expected}")

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"detail": "unauthorized"})
            return
        if self.path == "/health":
            self._write_json(HTTPStatus.OK, {"status": "READY"})
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._write_json(HTTPStatus.UNAUTHORIZED, {"detail": "unauthorized"})
            return
        if self.path != "/runsync":
            self._write_json(HTTPStatus.NOT_FOUND, {"detail": "not found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length))
            job_input = payload["input"]
            if not isinstance(job_input, dict):
                raise ValueError("input은 객체여야 합니다.")
            output = handle_input(job_input)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._write_json(HTTPStatus.BAD_REQUEST, {"status": "FAILED", "error": str(error)})
            return
        self._write_json(HTTPStatus.OK, {"status": "COMPLETED", "output": output})

    def log_message(self, _format: str, *_args: object) -> None:
        """요청 본문과 인증 헤더가 로그에 남지 않도록 기본 액세스 로그를 끈다."""


def main() -> None:
    host = os.getenv("POD_HOST", "0.0.0.0")
    port = int(os.getenv("POD_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), PodRequestHandler)
    print(f"embedding/rerank Pod 서버가 http://{host}:{port}에서 대기합니다.")
    server.serve_forever()


if __name__ == "__main__":
    main()
