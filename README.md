# OpenClaw in an OpenShell sandbox on OpenShift

Runs [OpenClaw](https://github.com/openclaw/openclaw) inside an [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) sandbox, talking to a local vLLM model through the [Praxis](https://github.com/praxis-proxy/ai) proxy. No image builds.

## How it fits together
```
openshell CLI (your laptop) --port-forward--> OpenShell gateway --Sandbox CR--> Agent Sandbox controller
                                                                              |
   vLLM (KServe)  <--  Praxis (proxy)  <--  OpenShell supervisor  <--  sandbox pod: OpenClaw
```
- The **gateway** (Helm chart) creates sandboxes when called. Nothing declarative creates one, so you create it with the `openshell` CLI through a port-forward (`scripts/03-create-sandbox.sh`).
- The sandbox runs OpenClaw as its entrypoint, with `ghcr.io/openclaw/openclaw` as the image and a filesystem/egress policy (`sandbox/policy.yaml`). Egress is limited to **Praxis** and read-only requests to `api.github.com` from `curl` (see "What the sandbox policy allows").
- A sandbox's `/sandbox` directory lives on its own PVC. `openshell sandbox stop` / `start` keep it; `openshell sandbox delete` deletes it.
The model is a self-hosted vLLM server (a KServe InferenceService). OpenClaw reaches it only through Praxis.

## Prerequisites
- OpenShift >= 4.19 (older kernels lack Landlock), a CNI that enforces NetworkPolicy, `oc`, `helm`, the [`openshell` CLI](https://github.com/NVIDIA/OpenShell/releases) (same version as the gateway chart, 0.1.6), cluster-admin
- A GPU node for vLLM. The InferenceService assumes one NVIDIA GPU (24 GB or more) and tolerates the `nvidia.com/gpu` taint. KServe / OpenShift AI is required.
- Egress for: ghcr.io, registry.redhat.io, huggingface.co (model download)

## Install
```bash
oc login ...
./scripts/00-prereqs.sh            # checks; installs the Agent Sandbox controller + Sandbox CRD (v1.0.8)
./scripts/01-install-openshell.sh  # OpenShell chart with SCC overlay + values/openshift-override.yaml
./scripts/02-apply.sh              # vLLM and Praxis
./scripts/03-create-sandbox.sh     # port-forwards the gateway and creates the sandbox with the CLI
```

## Use it
```bash
oc -n openshell-demo port-forward pod/default--openclaw 18789:18789   # then open http://127.0.0.1:18789
# gateway token (prints a secret):
oc -n openshell-demo exec default--openclaw -c agent -- \
  sh -c "sed -n 's/.*\"token\": *\"\([^\"]*\)\".*/\1/p' /sandbox/.openclaw/openclaw.json | head -1"
```
The sandbox pod is `<workspace>--<name>` (`default--openclaw`).

## Manage the sandbox
`03-create-sandbox.sh` registers the gateway as plaintext at port 8080. Port forward the gateway to your local machine at that port to manage your sandboxes
```bash
oc -n openshell-demo port-forward svc/openshell 8080:8080
openshell sandbox list
openshell sandbox stop openclaw      # keeps the sandbox and its /sandbox PVC
openshell sandbox start openclaw
openshell policy set openclaw --policy sandbox/policy.yaml   # apply a changed policy to the live sandbox
openshell sandbox exec openclaw -- ls /sandbox/.openclaw/workspace # see what the agent has written to its persistent workspace
openshell sandbox delete openclaw    # deletes the sandbox AND its /sandbox PVC
```
Re-run `./scripts/03-create-sandbox.sh` after a delete. It does nothing if the sandbox already exists.

## Tear down
```bash
./scripts/99-teardown.sh --dry-run   # show what would be deleted
./scripts/99-teardown.sh             # asks first; --yes skips the prompt
```

## What the sandbox policy allows
`sandbox/policy.yaml` is the whole policy. Anything it doesn't list is denied.

Network rules can be changed on a running sandbox: `openshell policy set openclaw --policy sandbox/policy.yaml`.

The filesystem, Landlock and process sections cannot lose paths or change on a live sandbox.


The namespace is `openshell-demo`. It is set in `manifests/kustomization.yaml` and the scripts, and also appears in service hostnames in `03-create-sandbox.sh`, `praxis.yaml` and `sandbox/policy.yaml`. Change all of them together.

## Known gaps
- The chart is marked experimental upstream. Kata (`sandbox.defaultRuntimeClassName`) is an optional extra and is untested.
- The gateway runs over plaintext HTTP with unauthenticated access, reachable only through a port-forward. Add OIDC/mTLS and a Route before sharing it.
