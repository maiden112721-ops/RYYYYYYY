from fastapi.testclient import TestClient

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


def test_wallet_cannot_overdraw():
    wallet = client.post('/api/wallets', json={'name': 'Savings'}).json()
    client.post('/api/transactions', json={'type': 'deposit', 'amount': '100', 'wallet_id': wallet['id']})
    assert client.get('/api/wallets').json()[0]['balance'] == 100
    response = client.post('/api/transactions', json={'type': 'withdraw', 'amount': '101', 'wallet_id': wallet['id']})
    assert response.status_code == 400
