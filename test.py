import requests

t = requests.get("https://github.com/tardyp/git-proxy.git/info/refs?service=git-upload-pack")
print t.content