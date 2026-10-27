import hashlib, json, os, shlex, sys, time
from google.protobuf.json_format import ParseDict
from openshell import SandboxClient
from openshell.errors import GatewayError
from openshell._proto import openshell_pb2 as pb

ENDPOINT = os.environ.get("OPENSHELL_ENDPOINT", "openshell.openshell-demo.svc:8080")
WS = os.environ.get("OPENSHELL_WORKSPACE", "default")
NAME = os.environ.get("SANDBOX_NAME", "openclaw")
PORT = os.environ.get("OPENCLAW_PORT", "18789")
FORCE = os.environ.get("FORCE_RECREATE", "false").lower() == "true"
BASE_URL, MODEL = os.environ["VLLM_BASE_URL"], os.environ["VLLM_MODEL_ID"]
if "CHANGE-ME" in BASE_URL + MODEL:
    sys.exit("Edit VLLM_BASE_URL / VLLM_MODEL_ID in the openclaw-model configMapGenerator first")

# VLLM_API_KEY: no auth on the model endpoint, any non-empty value.
# TMPDIR/SQLITE_TMPDIR: without these OpenClaw's SQLite fails inside the sandbox with
# "fts5: error creating shadow table ... unable to open database file" (it picks a temp dir the
# sandbox filesystem policy blocks). Verified: with them set, an agent turn returns a reply.
ENV = {"VLLM_API_KEY": "vllm-local", "TMPDIR": "/tmp", "SQLITE_TMPDIR": "/tmp"}

cmd = (f"openclaw onboard --non-interactive --accept-risk --skip-health --mode local "
       f"--auth-choice vllm --custom-base-url {shlex.quote(BASE_URL)} --custom-api-key vllm-local "
       f"--custom-model-id {shlex.quote(MODEL)} && exec openclaw gateway --port {PORT} --bind lan")
policy = json.load(open("/app/policy.json"))
spec = pb.SandboxSpec()
ParseDict({"policy": policy, "command": ["sh", "-c", cmd], "environment": ENV}, spec)

# Everything that defines the sandbox (policy, command, env, this script). When any of it changes
# the hash changes, and the sandbox is replaced. Unchanged config => pod restarts leave it alone.
HASH_KEY = "openclaw.demo/config-hash"
want = hashlib.sha256(json.dumps([policy, cmd, ENV, open("/app/launch.py").read()],
                                 sort_keys=True).encode()).hexdigest()[:16]

def delete_and_wait(c):
    try:
        c.delete(NAME, workspace=WS, allow_missing=True)
    except GatewayError as e:   # delete can hit a client deadline but still complete server-side
        print("delete:", str(e)[:120])
    for _ in range(90):
        try:
            c.get(NAME, workspace=WS); time.sleep(5)
        except Exception:
            return
    sys.exit("old sandbox still present after 450s")

with SandboxClient(ENDPOINT) as c:
    try:
        have = (c.get(NAME, workspace=WS).labels or {}).get(HASH_KEY)
        exists = True
    except Exception:
        have, exists = None, False
    if exists and (FORCE or have != want):
        print(f"config changed ({have} -> {want}) or forced; recreating sandbox")
        delete_and_wait(c)
        exists = False
    if exists:
        print(f"sandbox up to date ({want}); leaving it as is")
    else:
        c.create(workspace=WS, name=NAME, spec=spec, labels={HASH_KEY: want})
        print(f"sandbox created ({want}); OpenClaw gateway is its entrypoint")
    c.wait_ready(NAME, workspace=WS, timeout_seconds=600)
    print("sandbox ready")
