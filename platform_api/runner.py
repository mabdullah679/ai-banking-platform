from typing import Protocol

from platform_api.models import Job


class JobRunner(Protocol):
    """Anything that can take a job and turn it into running work."""

    def submit(self, job: Job) -> dict: ...


# Builds the Kubernetes Job manifest for a team's job: its namespace, limits, GPU and safe defaults.
def render_k8s_job(job: Job) -> dict:
    resources = {"cpu": str(job.cpu), "memory": f"{job.memory_gb}Gi"}
    limits = dict(resources)
    if job.gpu > 0:
        limits["nvidia.com/gpu"] = str(job.gpu)
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": f"{job.name}-{job.id}",
            "namespace": job.team,
            "labels": {"team": job.team, "kind": job.kind, "platform/job-id": str(job.id)},
        },
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 3600,
            "template": {
                "spec": {
                    "restartPolicy": "Never",
                    "securityContext": {"runAsNonRoot": True, "runAsUser": 10001},
                    "containers": [
                        {
                            "name": job.name,
                            "image": job.image,
                            "resources": {"requests": resources, "limits": limits},
                            "securityContext": {"allowPrivilegeEscalation": False},
                        }
                    ],
                }
            },
        },
    }


class LocalRunner:
    """Renders the manifest and records it. A KubernetesRunner would apply it to the cluster.

    The Kubernetes runner is NOT built: this runner never talks to a cluster.
    """

    # Renders the manifest for the job and returns it so it can be stored with the job.
    def submit(self, job: Job) -> dict:
        return render_k8s_job(job)


# Dependency: the runner the API uses. Tests replace this.
def get_runner() -> JobRunner:
    return LocalRunner()
