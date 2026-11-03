import json, time, urllib.request, urllib.parse, sys, gzip

UA = {"User-Agent": "Mozilla/5.0 (veille-hector)"}

def get(url, params=None, tries=6, timeout=40, data=None, headers=None):
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    h = dict(UA)
    if headers:
        h.update(headers)
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                if b[:2] == b"\x1f\x8b":
                    b = gzip.decompress(b)
                return b
        except Exception as e:
            last = e
            time.sleep(min(1.5 * (i + 1), 6))
    raise RuntimeError(f"echec {url[:90]} : {last}")

def jget(url, params=None, **kw):
    return json.loads(get(url, params, **kw))

def jpost(url, body, **kw):
    return json.loads(get(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, **kw))
