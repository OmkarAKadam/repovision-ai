# RepoVision AI Development Guidelines

- NEVER use --set-env-vars in deploy commands. Always use separate `gcloud run services update --update-env-vars` commands after deploying to preserve env vars.
