from fastapi.testclient import TestClient
from uuid import uuid4

from backend.app.main import app, letters, reminders, wallets, transactions

client = TestClient(app)


def setup_function():
    letters.clear()
    reminders.clear()
    wallets.clear()
    transactions.clear()


def test_letter_pin_gate():
    response = client.post('/api/letters', json={'title': 'Hello', 'body_html': '<script>x</script><p>Love</p>', 'pin': 'wrong'})
    assert response.status_code == 403
    response = client.post('/api/letters', json={'title': 'Hello', 'body_html': '<script>x</script><p>Love</p>', 'pin': '091425'})
    assert response.status_code == 201
    assert '<script>' not in response.json()['body_html']


def test_health_reports_memory_storage_for_local_tests():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['storage'] == 'memory'


def test_wallet_cannot_overdraw():
    wallet = client.post('/api/wallets', json={'name': 'Savings'}).json()
    client.post('/api/transactions', json={'type': 'deposit', 'amount': '100', 'wallet_id': wallet['id']})
    assert client.get('/api/wallets').json()[0]['balance'] == 100
    response = client.post('/api/transactions', json={'type': 'withdraw', 'amount': '101', 'wallet_id': wallet['id']})
    assert response.status_code == 400


def test_reminder_and_transaction_are_idempotent():
    client_id = str(uuid4())
    reminder_payload = {
        'client_id': client_id,
        'title': 'Dinner',
        'start_at': '2026-09-06T18:00:00Z',
        'end_at': '2026-09-06T19:00:00Z',
    }
    first_reminder = client.post('/api/reminders', json=reminder_payload)
    second_reminder = client.post('/api/reminders', json=reminder_payload)
    assert first_reminder.status_code == second_reminder.status_code == 201
    assert first_reminder.json()['id'] == second_reminder.json()['id']

    transaction_payload = {'client_id': str(uuid4()), 'type': 'deposit', 'amount': '100', 'merchant': 'Test'}
    first_transaction = client.post('/api/transactions', json=transaction_payload)
    second_transaction = client.post('/api/transactions', json=transaction_payload)
    assert first_transaction.status_code == second_transaction.status_code == 201
    assert first_transaction.json()['id'] == second_transaction.json()['id']
