"""Signal-aware shutdown: close event streams before Uvicorn drains requests."""
import uvicorn


class MonitorServer(uvicorn.Server):
    def __init__(self, config, app):
        super().__init__(config)
        self.monitor_app = app

    def handle_exit(self, sig, frame):
        self.monitor_app.state.shutting_down = True
        super().handle_exit(sig, frame)


def serve(app, host, port):
    config = uvicorn.Config(app, host=host, port=port, timeout_graceful_shutdown=5)
    MonitorServer(config, app).run()
