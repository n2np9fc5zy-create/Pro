"""Offline smoke test with isolated temporary storage; no external requests."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'hornet'))
with tempfile.TemporaryDirectory() as directory:
    os.environ['DB_PATH'] = str(Path(directory) / 'test.db')
    os.environ.pop('OPENAI_API_KEY', None)
    os.environ['AUTOPILOT'] = 'false'
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        assert client.get('/').status_code == 200
        assert client.get('/api/info').json()['connected_to_hornet'] is False
        first = client.post('/api/chats', json={'label': 'Тест A'}).json()['id']
        second = client.post('/api/chats', json={'label': 'Тест Б'}).json()['id']
        assert client.post(f'/api/chats/{first}/incoming', json={'text': 'Привет, это тест'}).status_code == 201
        result = client.post(f'/api/chats/{first}/reply')
        assert result.status_code == 200
        assert result.json()['sent_to_hornet'] is False
        assert '[ДЕМО БЕЗ ИИ]' in result.json()['reply']
        assert len(client.get(f'/api/chats/{first}/messages').json()) == 2
        assert client.get(f'/api/chats/{second}/messages').json() == []
        assert client.post(f'/api/chats/{first}/reply').status_code == 409
        os.environ['AUTOPILOT'] = 'true'
        auto = client.post(f'/api/chats/{second}/incoming', json={'text': 'Тест автогенерации'})
        assert auto.status_code == 201
        assert auto.json()['generated']['sent_to_hornet'] is False
        assert client.delete(f'/api/chats/{first}').status_code == 200
        assert client.get(f'/api/chats/{first}/messages').status_code == 404
print('PASS: panel, isolated histories, demo replies, autopilot, duplicate guard, deletion')
