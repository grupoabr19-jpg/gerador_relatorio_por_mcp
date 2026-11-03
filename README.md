# Google Analytics MCP Server (Experimental)

[![PyPI version](https://img.shields.io/pypi/v/analytics-mcp.svg)](https://pypi.org/project/analytics-mcp/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GitHub branch check runs](https://img.shields.io/github/check-runs/googleanalytics/google-analytics-mcp/main)](https://github.com/googleanalytics/google-analytics-mcp/actions?query=branch%3Amain++)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/analytics-mcp)](https://pypi.org/project/analytics-mcp/)
[![GitHub stars](https://img.shields.io/github/stars/googleanalytics/google-analytics-mcp?style=social)](https://github.com/googleanalytics/google-analytics-mcp/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/googleanalytics/google-analytics-mcp?style=social)](https://github.com/googleanalytics/google-analytics-mcp/network/members)
[![YouTube Video Views](https://img.shields.io/youtube/views/PT4wGPxWiRQ)](https://www.youtube.com/watch?v=PT4wGPxWiRQ)

This repo contains the source code for running a local
[MCP](https://modelcontextprotocol.io) server that interacts with APIs for
[Google Analytics](https://support.google.com/analytics).

Join the discussion and ask questions in the
[🤖-analytics-mcp channel](https://discord.com/channels/971845904002871346/1398002598665257060)
on Discord.

## Tools 🛠️

The server uses the
[Google Analytics Admin API](https://developers.google.com/analytics/devguides/config/admin/v1)
and
[Google Analytics Data API](https://developers.google.com/analytics/devguides/reporting/data/v1)
to provide several
[Tools](https://modelcontextprotocol.io/docs/concepts/tools) for use with LLMs.

### Retrieve account and property information 🟠

- `get_account_summaries`: Retrieves information about the user's Google
  Analytics accounts and properties.
- `get_property_details`: Returns details about a property.
- `list_google_ads_links`: Returns a list of links to Google Ads accounts for
  a property.
- `list_property_annotations`: Returns annotations for a property.
- `create_property_annotation`: Creates an annotation for a property (requires
  passing the `--allow-write` flag and the `analytics.edit` scope).

### Run core reports 📙

- `run_report`: Runs a Google Analytics report using the Data API.
- `export_report_to_csv`: Runs a report and saves all its rows as a local CSV
  file on the machine running the MCP server. Existing files are protected
  unless `overwrite` is explicitly set to `true`.
- `export_records_to_csv`: Saves records returned by another MCP data tool,
  such as Meta Ads Insights or Taplio post analytics, as a local CSV file.
- `run_funnel_report`: Runs a Google Analytics funnel report using the Data API.
- `get_custom_dimensions_and_metrics`: Retrieves the custom dimensions and
  metrics for a specific property.

### Run realtime reports ⏳

- `run_realtime_report`: Runs a Google Analytics realtime report using the
  Data API.

### Export reports 📥

Use `export_report_to_csv` with the same property, date ranges, dimensions, and
metrics as `run_report`, plus an `output_path` ending in `.csv`. The tool
retrieves every report page and creates the file on the machine running the MCP
server. It uses the existing Analytics read-only access; local file creation
does not require `--allow-write`. Set `overwrite` to `true` only when you want
to replace a file at that path.

For data returned by a different MCP server, pass its records array to
`export_records_to_csv` with an `output_path` ending in `.csv`. The tool
combines the keys across records into columns and serializes nested values as
JSON. Keep each data source in its own CSV because Meta Ads and LinkedIn
analytics have different schemas.

The workspace includes [`.vscode/mcp.json`](.vscode/mcp.json), which
configures the local Analytics server and connects Meta Ads and Taplio as
remote HTTP servers. VS Code will prompt for the Google Cloud project and the
remote servers' sign-in flows.

For Meta Ads reporting, the account needs the `ads_read` permission. Taplio's
analytics endpoints cap date ranges at 90 days and per-post results at 100
records per page; use its cursor to retrieve additional pages before exporting.
The export workflow is read-only. The remote servers may also expose write
tools, so disable those in VS Code's tool configuration for this MVP; campaign
changes, publishing, comments, outreach, and scraping are out of scope.

### Scheduled exports with GitHub Actions

The repository includes
[`.github/workflows/daily-marketing-report.yml`](.github/workflows/daily-marketing-report.yml)
and a collector that runs daily at 06:00 São Paulo time (09:00 UTC). It
re-queries the previous seven complete days to account for reporting delays
and upserts by date and dimensions. Run it manually with **Actions → Daily
marketing data → Run workflow** to verify setup before enabling the schedule.

The collector creates and writes only to `Coleta_GA4_Diario` and
`Coleta_MetaAds_Diario`; it does not modify existing source tabs or the
Dashboard. Counts and rates are stored as numbers. Configure repository
**Variables** and **Secrets**:

| Name | Type | Purpose |
| --- | --- | --- |
| `SPREADSHEET_ID` | Variable | Optional override for the shared spreadsheet ID already configured in the workflow. |
| `GA4_PROPERTY_ID` | Variable | Optional override for the GA4 property ID `415894822`; leave blank to use that default. |
| `META_AD_ACCOUNT_ID` | Variable | Meta ad account ID, with or without `act_`; leave blank to skip Ads. |
| `ENABLE_DAILY_SCHEDULE` | Variable | Set to `true` to enable scheduled runs. Manual runs remain available. |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Secret | Google Cloud Workload Identity Provider resource name. |
| `GCP_SERVICE_ACCOUNT` | Secret | Service account email used through Workload Identity Federation. |
| `META_ACCESS_TOKEN` | Secret | Meta access token with `ads_read`; required when Meta Ads is enabled. |

Set up Google Cloud Workload Identity Federation for this GitHub repository
using the [official GitHub Actions guide](https://github.com/google-github-actions/auth#preferred-workload-identity-federation).
Restrict the provider condition to this repository and grant the service
account read access to the GA4 property and edit access to the spreadsheet
(share the sheet with the service account email). Enable the Analytics Data
API and Google Sheets API in the Cloud project.

The Meta report is ad-level with daily `publisher_platform` and
`platform_position` breakdowns. The Meta token must have access to the account;
plan for its expiration and renewal. Never put tokens or credential files in
the repository.

This first scheduled version does **not** collect organic Facebook/Instagram
Page Insights or LinkedIn/Taplio metrics, and it does not update the existing
Dashboard. Instagram organic insights require a separate account ID and
permissions; Taplio's documented browser OAuth is not suitable for unattended
GitHub Actions. Those sources should be added only after their unattended
authentication and metric mapping are configured.

## Setup instructions 🔧

✨ Watch the [Google Analytics MCP Setup
Tutorial](https://youtu.be/nS8HLdwmVlY) on YouTube for a step-by-step
walkthrough of these instructions.

[![Watch the video](https://img.youtube.com/vi/nS8HLdwmVlY/mqdefault.jpg)](https://www.youtube.com/watch?v=nS8HLdwmVlY)

Setup involves the following steps:

1.  Configure Python.
1.  Configure credentials for Google Analytics.
1.  Configure Gemini.

### Configure Python 🐍

[Install pipx](https://pipx.pypa.io/stable/#install-pipx).

### Enable APIs in your project ✅

[Follow the instructions](https://support.google.com/googleapi/answer/6158841)
to enable the following APIs in your Google Cloud project:

- [Google Analytics Admin API](https://console.cloud.google.com/apis/library/analyticsadmin.googleapis.com)
- [Google Analytics Data API](https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com)

### Configure credentials 🔑

Configure your [Application Default Credentials
(ADC)](https://cloud.google.com/docs/authentication/provide-credentials-adc).
Make sure the credentials are for a user with access to your Google Analytics
accounts or properties.

Credentials must include the Google Analytics read-only scope:

```
https://www.googleapis.com/auth/analytics.readonly
```

If you plan to enable write tools (such as `create_property_annotation`) using
the `--allow-write` flag, your credentials must also include the edit scope:

```
https://www.googleapis.com/auth/analytics.edit
```

Check out
[Manage OAuth Clients](https://support.google.com/cloud/answer/15549257)
for how to create an OAuth client.

Here are some sample `gcloud` commands you might find useful:

- Set up ADC using user credentials and an OAuth desktop or web client after
  downloading the client JSON to `YOUR_CLIENT_JSON_FILE`.

  ```shell
  gcloud auth application-default login \
    --scopes https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform \
    --client-id-file=YOUR_CLIENT_JSON_FILE
  ```

- Set up ADC using service account impersonation.

  ```shell
  gcloud auth application-default login \
    --impersonate-service-account=SERVICE_ACCOUNT_EMAIL \
    --scopes=https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform
  ```

When the `gcloud auth application-default` command completes, copy the
`PATH_TO_CREDENTIALS_JSON` file location printed to the console in the
following message. You'll need this for the next step!

```
Credentials saved to file: [PATH_TO_CREDENTIALS_JSON]
```

### Configure Gemini

1.  Install [Gemini
    CLI](https://github.com/google-gemini/gemini-cli/blob/main/docs/get-started/installation.md)
    or [Gemini Code
    Assist](https://marketplace.visualstudio.com/items?itemName=Google.geminicodeassist).

1.  Create or edit the file at `~/.gemini/settings.json`, adding your server
    to the `mcpServers` list.

    Replace `PATH_TO_CREDENTIALS_JSON` with the path you copied in the previous
    step.

    We also recommend that you add a `GOOGLE_CLOUD_PROJECT` attribute to the
    `env` object. Replace `YOUR_PROJECT_ID` in the following example with the
    [project ID](https://support.google.com/googleapi/answer/7014113) of your
    Google Cloud project.

    ```json
    {
      "mcpServers": {
        "analytics-mcp": {
          "command": "pipx",
          "args": ["run", "analytics-mcp"],
          "env": {
            "GOOGLE_APPLICATION_CREDENTIALS": "PATH_TO_CREDENTIALS_JSON",
            "GOOGLE_CLOUD_PROJECT": "YOUR_PROJECT_ID"
          }
        }
      }
    }
    ```

    To enable write tools (e.g. `create_property_annotation`), append
    `"--allow-write"` to `"args"`: `["run", "analytics-mcp", "--allow-write"]`.

### Configure Claude Code

1.  Add the MCP server with the following command:

    Replace `PATH_TO_CREDENTIALS_JSON` with the path you copied in the previous
    step, and replace `YOUR_PROJECT_ID` with the
    [project ID](https://support.google.com/googleapi/answer/7014113) of your
    Google Cloud project.

    ```shell
    claude mcp add analytics-mcp \
      --scope user \
      -e "GOOGLE_APPLICATION_CREDENTIALS=PATH_TO_CREDENTIALS_JSON" \
      -e "GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID" \
      -- pipx run analytics-mcp
    ```

### Multi-tenant HTTP & End-User OAuth 🌐

To host `analytics-mcp` as a shared multi-tenant HTTP service (where each end
user signs in with their own Google account via OAuth 2.0 rather than using
server-side Application Default Credentials), start the server with
`--transport http`:

```shell
pipx run analytics-mcp \
  --transport http --stateless-http --host 0.0.0.0 --port 8080
```

- **Agent Framework OAuth (e.g. Google ADK)**: Configure per-user Google OAuth
  on `McpToolset` so end users are automatically prompted with a **Sign in**
  button in the chat UI, and can even combine Google Analytics MCP alongside
  other MCP servers in the same agent. Paired with `--stateless-http`, this
  mode is completely stateless and horizontally scalable across multiple
  replicas.
- **Native MCP OAuth 2.1 Server (`--oauth`)**: Pass `--oauth` (with
  `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and optional
  `ANALYTICS_MCP_ISSUER_URL` set) to enable the built-in MCP OAuth 2.1
  Authorization Server:

  ```shell
  export GOOGLE_OAUTH_CLIENT_ID="your-client-id.apps.googleusercontent.com"
  export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
  export ANALYTICS_MCP_ISSUER_URL="https://analytics-mcp.yourdomain.com"

  pipx run analytics-mcp \
    --transport http --stateless-http --oauth --host 0.0.0.0 --port 8080
  ```

  Note: The built-in `--oauth` provider stores dynamic client registrations,
  pending authorization state, and refresh tokens in process memory (run as a
  single instance or with sticky sessions; restarts require re-authentication).

See the complete walkthrough, Dockerfile, and runnable agent code in
[`examples/multi_tenant_adk_agent/README.md`](examples/multi_tenant_adk_agent/README.md).

## Try it out 🥼

Launch Gemini Code Assist or Gemini CLI and type `/mcp`. You should see
`analytics-mcp` listed in the results.

Here are some sample prompts to get you started:

- Ask what the server can do:

  ```
  what can the analytics-mcp server do?
  ```

- Ask about a Google Analytics property

  ```
  Give me details about my Google Analytics property with 'xyz' in the name
  ```

- Prompt for analysis:

  ```
  what are the most popular events in my Google Analytics property in the last 180 days?
  ```

- Ask about signed-in users:

  ```
  were most of my users in the last 6 months logged in?
  ```

- Ask about property configuration:

  ```
  what are the custom dimensions and custom metrics in my property?
  ```

## Contributing ✨

Contributions welcome! See the [Contributing Guide](CONTRIBUTING.md).
