from app.models.auth import StorageStatePayload

data = [{"name": "foo", "value": "bar", "domain": "example.com", "path": "/"}]
try:
    p = StorageStatePayload.model_validate(data)
    print("Success:", p)
except Exception as e:
    print("Error:", e)
