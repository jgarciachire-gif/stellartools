"""Public assets do not need to read or renew a signed user session."""
from starlette.middleware.sessions import SessionMiddleware


class SesionesSinRecursosEstaticos(SessionMiddleware):
    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope["type"] == "http" and (
            path.startswith("/static/") or path == "/service-worker.js"
        ):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)
