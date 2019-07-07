import os.path, tornado
from mgba.gba import GBA
from tornado import websocket, web, ioloop
from ringbuffer import RingBuffer

class Server:
    # Store all active clients in a set.
    clients = set()
    # Data to send to the client when entering.
    metadata = dict()
    # The emulator instance
    core = None

    # Stores all the commands in a ring buffer of size 1000
    all_logs = RingBuffer(1000)

    # mapping of keynames that the client will use
    KEYMAP = {GBA.KEY_A: 'a', GBA.KEY_B: 'b', GBA.KEY_SELECT: 'select', GBA.KEY_START: 'start', GBA.KEY_RIGHT: 'right',
              GBA.KEY_LEFT: 'left', GBA.KEY_UP: 'up', GBA.KEY_DOWN: 'down', GBA.KEY_R: 'r', GBA.KEY_L: 'l'}

    def __init__(self):
        self._settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), 'static'),
            static_path=os.path.join(os.path.dirname(__file__), 'static'),
            debug=True,
            autoreload=True
        )
        self._handlers = [
            (r'/', Server.IndexHandler),
            (r'/frame', Server.FrameHandler),
            (r'/debug', Server.DebugHandler),
            (r'/ws', Server.SocketHandler),
            (r'/favicon.ico', web.StaticFileHandler, { 'path': '.' })
        ]

        self.app = web.Application(self._handlers, **self._settings)

    class IndexHandler(web.RequestHandler):
        def get(self):
            self.render('index.html')

    class FrameHandler(web.RequestHandler):
        def get(self):
            self.render('frame.html')

    class DebugHandler(web.RequestHandler):
        def post(self):
            data = tornado.escape.json_decode(self.request.body)
            print("[DEBUG] ", data)
            self.write({"ok": True})

    class SocketHandler(websocket.WebSocketHandler):
        def open(self):
            Server.clients.add(self)
            self.write_message(Server.metadata)
            buffer_index = Server.all_logs.index
            if buffer_index > 0:
                self.write_message({ 'event': 'all logs', 'data': Server.all_logs.get_k_recent(buffer_index) })


        def on_message(self, msg):
            if Server.core is None:
                client.captureMessage('Socket event with undefined emulator core')
                return

            split = msg.split("-")
            action = split[0]
            key = split[1]
            command_string = "%s" % (Server.KEYMAP.get(int(key)))
            Server.all_logs.append(command_string)

            if action == "down":
                Server.core.key_down(int(key))
            elif action == "up":
                Server.core.key_up(int(key))
            elif action == "press":
                Server.core.push_key(int(key))
            # Send the recent command to the user
            for client in Server.clients:
                client.write_message({'event': 'last log', 'data': command_string})

        def on_close(self):
            Server.clients.remove(self)

        def check_origin(self, orgin):
            return True

    def set_core(self, _core):
        Server.core = _core
        Server.metadata['event'] = 'metadata'
        Server.metadata['width'] = _core.width
        Server.metadata['height'] = _core.height

    def emit_frame(self, data):
        if data is None or len(data) <= 0:
            return
        @tornado.gen.coroutine
        def stream_frame(self):
            for client in Server.clients:
                yield client.write_message(data, binary=True)

        tornado.ioloop.IOLoop.current().spawn_callback(stream_frame, self)

    def listen(self, port):
        self.app.listen(port)


if __name__ == '__main__':
    Server().listen(8888)
    ioloop.IOLoop.instance().start()
