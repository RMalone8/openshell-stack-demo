# OpenClaw in an OpenShell sandbox on OpenShift

Runs [OpenClaw](https://github.com/openclaw/openclaw) inside an [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) sandbox, talking to a local vLLM model through the [Praxis](https://github.com/praxis-proxy/ai) proxy. No image builds.

## How it fits together
```
openclaw-launcher (Deployment) --SDK--> OpenShell gateway --Sandbox CR--> Agent Sandbox controller
                                                                              |
   vLLM (KServe)  <--  Praxis (proxy)  <--  OpenShell supervisor  <--  sandbox pod: OpenClaw
```
- The **gateway** (Helm chart) creates sandboxes when called. Nothing declarative creates one, so the **launcher** calls it.
- The sandbox runs OpenClaw as its entrypoint, with `ghcr.io/openclaw/openclaw` as the image and a filesystem/egress policy (`manifests/launcher/policy.json`).
- Egress from the sandbox is limited to **Praxis**, which forwards all paths to vLLM.
- The launcher stamps the sandbox with a hash of its config. Changing the script, policy or model settings and running `oc apply -k` recreates the sandbox. An unchanged config is left alone.

## Prerequisites
- OpenShift >= 4.19 (older kernels lack Landlock), a CNI that enforces NetworkPolicy, `oc`, `helm`, cluster-admin
- A GPU node for vLLM. The InferenceService assumes one NVIDIA GPU (24 GB or more) and tolerates the `nvidia.com/gpu` taint. KServe / OpenShift AI is required.
- Egress for: ghcr.io, registry.redhat.io, huggingface.co (model download), PyPI (launcher)

## Install
```bash
oc login ...
./scripts/00-prereqs.sh            # checks; installs the Agent Sandbox controller + Sandbox CRD (v1.0.8)
./scripts/01-install-openshell.sh  # OpenShell chart with SCC overlay + values/openshift-override.yaml
./scripts/02-apply.sh              # vLLM, Praxis, launcher; creates the sandbox
```

## Use it
```bash
oc -n openshell-demo port-forward pod/default--openclaw 18789:18789   # then open http://127.0.0.1:18789
# gateway token (prints a secret):
oc -n openshell-demo exec default--openclaw -c agent -- \
  sh -c "sed -n 's/.*\"token\": *\"\([^\"]*\)\".*/\1/p' /sandbox/.openclaw/openclaw.json | head -1"
```
The sandbox pod is `<workspace>--<name>` (`default--openclaw`). Launcher logs: `oc -n openshell-demo logs -f deploy/openclaw-launcher`.

## Tear down
```bash
./scripts/99-teardown.sh --dry-run   # show what would be deleted
./scripts/99-teardown.sh             # asks first; --yes skips the prompt
```
`oc delete -k manifests` alone leaves the gateway and sandbox running: the sandbox and supervisor are created by the gateway at runtime, and the gateway comes from Helm. The script removes manifests, then sandboxes, then the gateway release and its data PVC. Add `--delete-namespace` to drop the namespace, or `--agent-sandbox` to remove the cluster-wide Agent Sandbox controller and CRD (affects every namespace).

## Configure
| What | Where |
|---|---|
| Model name and Praxis URL | `configMapGenerator` in `manifests/kustomization.yaml` (model ID = InferenceService name) |
| Model, GPU, context length | `manifests/vllm-gpu-inferenceservice.yaml` |
| Sandbox filesystem / egress policy | `manifests/launcher/policy.json` |
| Sandbox command, env, recreate logic | `manifests/launcher/launch.py` |
| Praxis routing | `manifests/praxis.yaml` |
| Gateway chart values, sandbox image | `values/openshift-override.yaml` |

The namespace is `openshell-demo`. It is set in `manifests/kustomization.yaml` and the scripts, and also appears in service hostnames in `launch.py`, `kustomization.yaml`, `praxis.yaml` and `policy.json`. Change all of them together. `policy/openclaw-policy.yaml` is a reference copy only.

## Known gaps
- No Route for the UI. OpenShell has service forwarding (a gateway-managed URL), but it needs a wildcard Route that preserves the `Host` header, which is not set up here.
- The chart is marked experimental upstream. Kata (`sandbox.defaultRuntimeClassName`) is an optional extra and is untested.
- Old generated ConfigMaps are not pruned.
