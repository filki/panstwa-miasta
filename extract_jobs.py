import json

def extract_opis(obj, result):
    if isinstance(obj, dict):
        if "opis" in obj:
            result.add(obj["opis"])
        for k, v in obj.items():
            extract_opis(v, result)
    elif isinstance(obj, list):
        for item in obj:
            extract_opis(item, result)

d = json.load(open("data/hierarchiczny.json"))
res = set()
extract_opis(d, res)
with open("data/raw_jobs.txt", "w", encoding="utf-8") as f:
    for opis in sorted(res):
        f.write(opis + "\n")
