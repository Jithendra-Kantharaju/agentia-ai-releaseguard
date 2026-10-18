import {AgentiaCommand, getAgentiaHost} from '@copado/agentia-plugin-sdk'
import {Flags} from '@oclif/core'

/**
 * ReleaseGuard preflight.
 *
 * Collects verified Copado context using ONLY the supported plugin host API (no credentials, no
 * subprocesses, no files): the story, the signed-in user and the governance health check.
 * Pipe it into the Python core:
 *   agentia releaseguard preflight --json > preflight.json
 *   python -m releaseguard check --preflight preflight.json ...
 */
export default class ReleaseguardPreflight extends AgentiaCommand {
  static override description = 'Collect verified Copado context (story, user, governance health) for ReleaseGuard'
  static override examples = [
    '<%= config.bin %> <%= command.id %>',
    '<%= config.bin %> <%= command.id %> --json > preflight.json',
    '<%= config.bin %> <%= command.id %> --story US-0000001',
  ]
  static override flags = {
    story: Flags.string({description: 'Work item Id or name (default: the active story)'}),
  }

  public async run() {
    const {flags} = await this.parse(ReleaseguardPreflight)
    // Keep this list in sync with "agentia.requires" in package.json.
    const host = getAgentiaHost({
      requires: ['format.table', 'organization.healthCheck', 'user.get', 'work.getWorkItem', 'workspace.current'],
    })

    const [user, story, workspace, health] = await this.withSpinner('Collecting Copado context', () =>
      Promise.all([
        host.user.get(),
        host.work.getWorkItem(flags.story),
        host.workspace.current(),
        host.organization.healthCheck(),
      ]),
    )

    const summarize = (status: string) =>
      health.checks
        .filter((check) => check.status === status)
        .map((check) => ({
          checkId: check.checkId,
          fixGuidance: check.fixGuidance ?? null,
          name: check.name,
          severity: check.severity ?? null,
        }))
    const failing = summarize('fail')
    const warnings = summarize('warn')

    const payload = {
      generatedAt: new Date().toISOString(),
      orgHealth: {failing, summary: health.summary, warnings},
      schema: 'releaseguard.preflight/1',
      user: {fullName: user.fullName ?? null, id: user.id, username: user.username ?? null},
      workItem: {
        acceptanceCriteria: story.acceptanceCriteria ?? null,
        baseBranch: story.baseBranch ?? null,
        id: story.id,
        name: story.name ?? null,
        priority: story.priority ?? null,
        projectName: story.projectName ?? null,
        status: story.status ?? null,
        title: story.title ?? null,
      },
      workspace: {
        baseBranch: workspace.baseBranch ?? null,
        branch: workspace.branch ?? null,
        workItemName: workspace.workItemName ?? null,
        workItemTitle: workspace.workItemTitle ?? null,
      },
    }

    this.display(() => {
      this.log(
        host.format.table(
          [
            {field: 'story', header: 'Story'},
            {field: 'status', header: 'Status'},
            {field: 'user', header: 'Signed-in user'},
            {field: 'fail', header: 'Health fail', align: 'right'},
            {field: 'warn', header: 'Health warn', align: 'right'},
          ],
          [
            {
              fail: health.summary.fail,
              status: story.status ?? '-',
              story: story.name ?? story.id,
              user: user.username ?? user.fullName ?? user.id,
              warn: health.summary.warn,
            },
          ],
        ),
      )
      if (failing.length > 0) {
        this.log('')
        this.log(
          host.format.table(
            [
              {field: 'name', header: 'Failing governance check', wrap: true},
              {field: 'severity', header: 'Severity'},
            ],
            failing.map((check) => ({name: check.name, severity: check.severity ?? '-'})),
          ),
        )
      }
      this.log('')
      this.log('Save this for ReleaseGuard:  agentia releaseguard preflight --json > preflight.json')
    })

    return payload
  }
}
