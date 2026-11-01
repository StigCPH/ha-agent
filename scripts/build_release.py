"""Build the HA HACS ZIP; identity files are never packaged."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

def build(root, output, tag=None):
    component=root/"custom_components"/"ha_agent"
    manifest=json.loads((component/"manifest.json").read_text())
    if tag and tag.removeprefix("v")!=manifest["version"]:
        raise ValueError("Tag and committed version differ")
    output.mkdir(parents=True,exist_ok=True)
    archive=output/"ha_agent.zip"
    with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
        for p in sorted(component.rglob("*")):
            relative=p.relative_to(component)
            if not p.is_file() or any(part.startswith(".") or part=="__pycache__" for part in relative.parts):
                continue
            if p.suffix in {".py",".json",".yaml",".png",".svg"} or relative.as_posix()=="agent_instructions.txt":
                z.write(p,relative.as_posix())
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    (output/"SHA256SUMS").write_text(digest+"  ha_agent.zip\n")
    return {"version":manifest["version"],"sha256":digest}

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--tag")
    args=parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1],Path("dist"),args.tag)))
