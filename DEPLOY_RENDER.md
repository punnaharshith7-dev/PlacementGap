# Deploy PlacementGap to Render

This Blueprint builds the React app into the FastAPI image and serves both from one HTTPS origin. It also provisions a private Render Postgres database and persistent disk for authentication, run records, caches, and reports. Keeping the UI and API on one origin keeps OAuth callbacks and session cookies aligned.

## Before creating resources

The Blueprint uses paid compute, a 1 GB persistent disk, and paid Postgres so the app stays awake and its data survives redeploys. Render shows the plan and monthly estimate before you apply the Blueprint. Review that total before confirming creation.

The initial configuration uses fixture-backed job data and disables paid LLM calls, so the app can start without an AI provider key. OAuth and email OTP require the provider and SMTP values described below.

## Create the Render Blueprint

1. Push the project to the GitHub branch you want Render to deploy. The repository must contain `render.yaml` at its root.
2. In Render, choose **New + → Blueprint** and connect the `PlacementGap` repository.
3. Select the intended branch and inspect the resources from `render.yaml`.
4. Enter SMTP and OAuth credentials in Render's secret fields, or add them under the web service's **Environment** page after creation. Keep them in Render; do not put them in Git or this repository.
5. Review the paid resource estimate and apply only when you are ready to create the resources.

Render builds the root `Dockerfile`, creates PostgreSQL 16 with public IP access disabled, generates `AUTH_SECRET`, mounts persistent storage at `/var/data`, and serves the app at its public HTTPS URL.

## Finish OAuth setup

After the first deploy, copy the app's public Render URL, for example `https://placementgap-app.onrender.com`. Add these callback URLs to the matching provider applications, replacing the example host with the exact URL Render assigned:

- Google: `https://placementgap-app.onrender.com/auth/google/callback`
- Microsoft: `https://placementgap-app.onrender.com/auth/microsoft/callback`
- GitHub: `https://placementgap-app.onrender.com/auth/github/callback`

For Google, add the app URL as an authorized JavaScript origin and the callback as an authorized redirect URI. For Microsoft, register the callback as a **Web** redirect URI. For GitHub, use it as the Authorization callback URL. Save the matching client IDs and secrets in the Render service environment, then redeploy.

## Configure email OTP

Set `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM` in the Render service environment. The Blueprint defaults to port `587` with STARTTLS (`SMTP_USE_SSL=false`). For implicit TLS, use port `465` and set `SMTP_USE_SSL=true`. Redeploy after changing environment values.

## Verify the deployed app

- Open the service's public HTTPS URL. The landing page, sign-in, and dashboard are served by the same service.
- Open `/health`; it should return the PlacementGap health response.
- Create an account and confirm the email OTP arrives.
- Test each configured OAuth provider and ensure it returns to the same Render host.
- Start an analysis, approve its plan, and download the generated report.

The default Blueprint runs with fixture-backed job data and no LLM calls. Change those flags only after configuring and validating the corresponding live providers.
