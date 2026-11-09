import os, re, sys, urllib.request, urllib.parse
out = sys.argv[1]; start = sys.argv[2]
seen = set(); queue = [start]
def local(url):
    p = urllib.parse.urlparse(url)
    return os.path.join(out, p.netloc, p.path.lstrip('/'))
while queue:
    url = queue.pop()
    if url in seen: continue
    seen.add(url)
    path = local(url)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not url.startswith("https://") and not url.startswith("http://"): continue
        try:
            data = urllib.request.urlopen(url, timeout=30).read()  # nosec - script local
        except Exception as e:
            print("FALHA", url, e); continue
        open(path, 'wb').write(data)
    text = open(path, encoding='utf-8', errors='ignore').read()
    for loc in re.findall(r'schemaLocation="([^"]+\.xsd)"', text):
        queue.append(urllib.parse.urljoin(url, loc))
print(len(seen), "schemas")
