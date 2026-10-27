# OpenClaw + OpenShell on OpenShift (demo scaffold)

**Status: unverified scaffold.** Nothing here has been run against a cluster. No upstream repo combines the two on OpenShift (checked 2026-10-27), so this stitches together the NVIDIA OpenShell chart, its OpenShift guide, and the OpenClaw-in-sandbox pattern from `davidhayesbc/openclaw-openshell`.

## Architecture
OpenShell's gateway runs as a StatefulSet in `openshell`. It creates sandbox pods through the Agent Sandbox CRD (`agents.x-k8s.io`). **OpenClaw runs inside a sandbox**, as the workload, with an OpenShell policy controlling filesystem and egress. It is not a separate Deployment.

## Prerequisites
- OpenShift >= 4.19 (older RHCOS kernels lack Landlock, so sandbox startup fails)
- CNI that enforces NetworkPolicy (OVN-Kubernetes does)
- `oc`, `helm`, `openshell` CLI; cluster-admin for the Agent Sandbox CRDs
- A registry your cluster can pull from, and a model endpoint (hosted API or in-cluster vLLM)

## Steps
```bash
oc login ...
./scripts/00-prereqs.sh            # checks + Agent Sandbox operator/CRDs (v1.0.8)
./scripts/01-install-openshell.sh  # chart + SCC overlay + override (sandbox.image = ghcr.io/openclaw/openclaw)
# edit manifests/launcher.yaml ConfigMap openclaw-model (VLLM_BASE_URL, VLLM_MODEL_ID) and fill in vllm-gpu-inferenceservice.yaml
./scripts/02-apply.sh              # launcher creates the sandbox and starts `openclaw gateway`
```
No image build: the sandbox uses the official prebuilt `ghcr.io/openclaw/openclaw`. `policy/openclaw-policy.yaml` is not applied automatically yet (see below).

## Open questions / likely rough edges
- Chart is marked **Experimental** upstream.
- `manifests/launcher.yaml` uses SDK calls documented upstream (`create`, `wait_ready`, `exec`), but the existence check (`get`), the exec result fields, and `pip install openshell` at pod start are unverified. The pod needs PyPI egress.
- Whether the official OpenClaw image works as an OpenShell sandbox workload (it runs as `node`; OpenShift assigns another UID) is untested.
- Applying `policy/openclaw-policy.yaml` declaratively isn't wired up; use `openshell policy set` or find the SDK/gateway-default equivalent. Until then OpenShell's default policy applies.
- OpenClaw's UI on :18789 is not exposed (no Route/Service): the sandbox pod is gateway-managed. Use `openshell` port forwarding for now.
- Sandbox startup fails if the runtime profile blocks nested seccomp user-notification or Landlock; if so, check the cluster's seccomp/SCC profile.
- OpenClaw's own UI/gateway on :18789 is reached via `openshell sandbox ssh-config` + SSH tunnel (see the hayesbc scripts), not an OpenShift Route.

## Going further
TLS/Route/OIDC options (BackendTLSPolicy on 4.22+, passthrough Route + cert-manager) are in the upstream guide: docs/kubernetes/openshift.mdx in NVIDIA/OpenShell.
