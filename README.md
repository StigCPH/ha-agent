# HA

A Microsoft Foundry connection for Home Assistant with three entry points:

- A reusable **AI Task** entity for text and structured-data tasks.
- A **conversation** entity for tool-free assistance.
- Evidence-checked **school plan previews** from an existing Aula sensor.

The Foundry agent, Entra application and certificate can all be named **HA**.
The integration uses OAuth 2.0 client credentials with a local certificate.
Private keys remain in the configuration directory, outside the integration and
outside the release ZIP. Tokens are cached in memory and renewed automatically.

## First-test behavior

School-plan analysis separates homework, packing items, practical events and
informational notes. Every item carries a source quote, a date when established,
and a confidence flag. It does not infer homework from classroom reading alone.
Lunch, water bottles, trip bags and library books are included when supported by
the source. Related packing items are grouped for the same trip.

This version previews results only. It does not create reminders, calendar events
or notifications, and does not expose device-control tools to the agent.
Generic AI Task and conversation calls remain available for other supplied tasks.

## Installation

1. Install **StigCPH/ha-agent** through HACS as a custom integration repository.
2. Keep a private RSA application key and its matching X.509 certificate under a
   dedicated directory inside the HA configuration folder. Restrict key permissions.
3. Register the public certificate on a dedicated Entra application. Create its
   service principal and assign **Foundry Agent Consumer** only at the target
   agent scope; avoid project-wide management roles.
4. Create the Foundry prompt agent using `agent_instructions.txt` and the desired
   existing model deployment. Pin the agent endpoint to the reviewed version.
   Enable its Responses protocol with Microsoft Entra/RBAC authorization.
5. Add **HA** under Settings > Devices & services. Enter the project endpoint,
   tenant ID, application client ID, agent name and local key/certificate paths.
   Setup validates OAuth without submitting an AI inference task.
6. Optionally select an existing Aula sensor and current/next week. Automatic
   analysis is off by default.

The cloud agent uses its own stable endpoint:
`{project}/agents/{agent}/endpoint/protocols/openai/responses`.
Other agents and the project's management APIs are not needed at runtime.

## Testing a school plan

Press **Analyze weekplan**, or call `ha_agent.analyze_weekplan` with response
data enabled. The **School plan** sensor contains the preview's summary and items.
The source sensor must provide `ugeplan` and/or `ugeplan_next` attributes.

Unchanged successful source data is reused without another model request.
In-flight requests are deduplicated. Failed or uncertain attempts are retained
across restarts and are not replayed automatically. Review the outcome before
using `force: true` to explicitly submit another request. Existing good previews
remain visible when a later analysis fails.

Automatic analysis, if enabled, reacts to source changes and uses the same cache
and uncertainty guard. It does not send reminders.

## Other tasks

Select the **HA AI Task** entity in `ai_task.generate_data` actions, or select the
**HA** conversation entity in Assist. Structured AI Task results use the requested
schema. This release accepts text only; attachments and device-control tools are
not enabled. The agent has access only to the context supplied with the request.

## Credentials and maintenance

The local certificate's expiry is a real lifecycle limit. Rotate its certificate
registration and local files before expiry, then reload the integration.
Reconfigure the connection through the UI when identifiers or file paths change.
Never publish key files, access tokens, actual school content or configuration
exports. Public regression cases use fictitious content.

## Development and releases

Use Python 3.14:
`python -m pip install -r requirements.test.txt`, then `python -m pytest -v`.

A release tests the exact reviewed commit, verifies that its tag matches the
committed manifest version, and packages only component source/assets.
HACS follows this repository's releases. The Aula data-source fork is independent.

Microsoft references:
- https://learn.microsoft.com/en-us/entra/identity-platform/certificate-credentials
- https://learn.microsoft.com/en-us/azure/foundry/concepts/rbac-foundry
- https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/agent-endpoint-authorization
