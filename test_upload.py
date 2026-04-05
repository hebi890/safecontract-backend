import sys
import requests

if len(sys.argv) < 2:
    print("Użycie: python test_upload.py sciezka_do_pliku.pdf")
    sys.exit(1)

file_path = sys.argv[1]

url = "http://127.0.0.1:8000/documents/upload"

with open(file_path, "rb") as f:
    files = {"file": f}
    response = requests.post(url, files=files)

print("Status:", response.status_code)
print("Response JSON:")
print(response.json())
