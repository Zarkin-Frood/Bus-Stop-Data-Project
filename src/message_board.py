import json
import os
import time

class Message:
    def __init__(self, message_id, user, text, timestamp, stop_id=None, image_path=None):
        self.message_id = message_id
        self.user = user
        self.text = text
        self.timestamp = timestamp
        self.stop_id = stop_id
        self.image_path = image_path

class MessageBoardService:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.messages = []
        self._load()

    def _file_path(self):
        return os.path.join(self.data_dir, "messages.json")

    def _load(self):
        os.makedirs(self.data_dir, exist_ok=True)
        try:
            with open(self._file_path(), "r", encoding="utf-8") as f:
                raw = json.load(f)
        except FileNotFoundError:
            raw = []
        self.messages = [Message(**m) for m in raw]

    def _save(self):
        os.makedirs(self.data_dir, exist_ok=True)
        raw = [m.__dict__ for m in self.messages]
        with open(self._file_path(), "w", encoding="utf-8") as f:
            json.dump(raw, f)

    def add_message(self, user, text, stop_id=None, image_path=None):
        message_id = int(time.time() * 1000)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        msg = Message(message_id, user, text, timestamp, stop_id, image_path)
        self.messages.append(msg)
        self._save()
        return msg

    def list_messages(self, stop_id=None):
        if stop_id is None:
            return list(self.messages)
        return [m for m in self.messages if m.stop_id == stop_id]
