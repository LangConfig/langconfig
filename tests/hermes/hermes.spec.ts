import { expect, test, type Page, type Route } from '@playwright/test';

type Draft = {
  id: number;
  title: string;
  artifact_type: string;
  payload_json: Record<string, unknown>;
  status: string;
  validation_result: Record<string, unknown>;
  apply_result?: Record<string, unknown>;
};

declare global {
  interface Window {
    hermesFixtureStreams: Array<{
      closed: boolean;
      onmessage: ((event: MessageEvent) => void) | null;
    }>;
    unmountHermesFixture: () => void;
  }
}

async function mountWorkspace(
  page: Page,
  applyResult: Record<string, unknown> = { artifact_type: 'workflow', action: 'created', workflow_id: 91 },
) {
  const drafts: Draft[] = [
    {
      id: 21,
      title: 'Saved review fixture',
      artifact_type: String(applyResult.artifact_type),
      payload_json: { name: 'ORIGINAL' },
      status: 'validated',
      validation_result: { valid: true, marker: 'original-validation' },
    },
    {
      id: 20,
      title: 'Second fixture',
      artifact_type: 'workflow',
      payload_json: { name: 'SECOND' },
      status: 'validated',
      validation_result: { valid: true },
    },
  ];
  const appliedIds: number[] = [];
  let createRoute: Route | undefined;
  let eventsRoute: Route | undefined;
  let runCount = 0;
  const unexpectedRequests: string[] = [];

  await page.addInitScript(() => {
    window.hermesFixtureStreams = [];
    // Control transport completion while exercising the real React lifecycle.
    window.EventSource = class {
      closed = false;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: (() => void) | null = null;
      constructor() {
        window.hermesFixtureStreams.push(this);
      }
      close() {
        this.closed = true;
      }
    } as unknown as typeof EventSource;
  });
  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname.replace(/\/$/, '');
    let data: unknown;
    if (path === '/api/projects') {
      data = [{ id: 1, name: 'Review project', status: 'active' }];
    } else if (path === '/api/platform-brain/status') {
      data = { source_count: 0 };
    } else if (path === '/api/codex/status') {
      data = { installed: true, logged_in: true, version: 'fixture' };
    } else if (path === '/api/hermes/drafts' && request.method() === 'GET') {
      data = drafts;
    } else if (path === '/api/hermes/drafts' && request.method() === 'POST') {
      createRoute = route;
      return;
    } else if (path.endsWith('/apply')) {
      appliedIds.push(Number(path.split('/').at(-2)));
      const draft = drafts.find((candidate) => candidate.id === appliedIds.at(-1))!;
      draft.status = 'applied';
      draft.apply_result = applyResult;
      data = { draft, apply_result: applyResult };
    } else if (path === '/api/codex/runs') {
      data = { id: `fixture-run-${++runCount}`, mode: 'exec', status: 'running' };
    } else if (path.endsWith('/events')) {
      eventsRoute = route;
      return;
    } else {
      unexpectedRequests.push(`${request.method()} ${path}`);
      await route.abort();
      return;
    }
    await route.fulfill({ json: data });
  });
  await page.goto('/tests/hermes/fixture.html');
  const saved = page.getByRole('button', { name: 'Saved review fixture' });
  await expect(saved).toBeEnabled();
  await saved.click();
  const apply = page.getByRole('button', { name: 'Apply', exact: true });
  await expect(apply).toBeEnabled();

  return {
    saved,
    apply,
    validate: page.getByRole('button', { name: 'Validate', exact: true }),
    draft: page.getByRole('button', { name: 'Draft', exact: true }),
    payload: page.locator('textarea').nth(1),
    title: page.locator('input').nth(0),
    artifact: page.locator('select'),
    appliedIds,
    unexpectedRequests,
    async finishCreate() {
      await expect.poll(() => Boolean(createRoute)).toBe(true);
      const draft = {
        ...createRoute!.request().postDataJSON(),
        id: 22,
        status: 'validated',
        validation_result: { valid: true },
      };
      drafts.unshift(draft);
      await createRoute!.fulfill({ json: draft });
      return draft as Draft;
    },
    async waitForCreate() {
      await expect.poll(() => Boolean(createRoute)).toBe(true);
    },
    async waitForEvents() {
      await expect.poll(() => Boolean(eventsRoute)).toBe(true);
    },
    async finishOldEvents() {
      await eventsRoute!.fulfill({ json: { events: [{ type: 'run.completed', message: 'old run result' }] } });
    },
  };
}

for (const field of ['payload', 'title', 'artifact'] as const) {
  test(`editing ${field} invalidates saved draft approval and validation`, async ({ page }) => {
    const ui = await mountWorkspace(page);
    if (field === 'artifact') {
      await ui.artifact.selectOption('schedule');
    } else {
      await ui[field].fill(field === 'payload' ? '{"name":"EDITED"}' : 'Edited title');
    }
    await expect(ui.apply).toBeDisabled();
    await expect(ui.validate).toBeDisabled();
    await expect(page.locator('pre').filter({ hasText: 'original-validation' })).toHaveCount(0);
    expect(ui.appliedIds).toEqual([]);
    expect(ui.unexpectedRequests).toEqual([]);
  });
}

for (const editFirst of [true, false]) {
  test(`pending creation locks controls and selects the created draft (edited=${editFirst})`, async ({ page }) => {
    const ui = await mountWorkspace(page);
    if (editFirst) await ui.payload.fill('{"name":"EDITED"}');
    await ui.draft.click();
    await ui.waitForCreate();
    for (const control of [ui.payload, ui.title, ui.artifact, ui.saved, ui.apply, ui.validate]) {
      await expect(control).toBeDisabled();
    }
    const created = await ui.finishCreate();
    await expect(ui.apply).toBeEnabled();
    await ui.apply.click();
    await expect(ui.draft).toBeEnabled();
    expect(ui.appliedIds).toEqual([22]);
    expect(created.payload_json).toEqual({ name: editFirst ? 'EDITED' : 'ORIGINAL' });
    expect(ui.unexpectedRequests).toEqual([]);
  });
}

test('failed activation remains visible after applying, refreshing, and reselecting a draft', async ({ page }) => {
  const reason = 'Saved disabled: File watcher service is not running';
  const ui = await mountWorkspace(page, {
    artifact_type: 'trigger',
    action: 'created',
    trigger_id: 91,
    activation: { status: 'failed', message: reason },
  });
  await ui.apply.click();
  await expect(ui.draft).toBeEnabled();
  const result = page.locator('pre').filter({ hasText: reason });
  await expect(result).toBeVisible();
  await expect(result).toContainText('"status": "failed"');
  await expect(page.locator('pre').filter({ hasText: 'original-validation' })).toHaveCount(0);

  await page.getByRole('button', { name: 'Refresh', exact: true }).click();
  await expect(ui.draft).toBeEnabled();
  await expect(result).toBeVisible();

  await page.getByRole('button', { name: 'Second fixture' }).click();
  await expect(result).toHaveCount(0);
  await expect(page.locator('pre').filter({ hasText: '"valid": true' })).toBeVisible();
  await ui.saved.click();
  await expect(result).toBeVisible();
  expect(ui.unexpectedRequests).toEqual([]);
});

test('draft selection and edits retain the stream; unmount closes it', async ({ page }) => {
  const ui = await mountWorkspace(page);
  await page.getByRole('button', { name: 'Run', exact: true }).click();
  await expect.poll(() => page.evaluate(() => window.hermesFixtureStreams.length)).toBe(1);
  await page.getByRole('button', { name: 'Second fixture' }).click();
  await ui.payload.fill('{"name":"EDITED"}');
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  expect(await page.evaluate(() => window.hermesFixtureStreams[0].closed)).toBe(false);
  await page.evaluate(() => window.unmountHermesFixture());
  expect(await page.evaluate(() => window.hermesFixtureStreams[0].closed)).toBe(true);
  expect(ui.unexpectedRequests).toEqual([]);
});

test('a delayed terminal response from an old stream cannot overwrite its replacement', async ({ page }) => {
  const ui = await mountWorkspace(page);
  const run = page.getByRole('button', { name: 'Run', exact: true });
  await run.click();
  await expect.poll(() => page.evaluate(() => window.hermesFixtureStreams.length)).toBe(1);
  await page.evaluate(() => window.hermesFixtureStreams[0].onmessage!(new MessageEvent('message', {
    data: JSON.stringify({ type: 'run.completed' }),
  })));
  await ui.waitForEvents();
  await run.click();
  await expect(page.getByText('fixture-run-2', { exact: true })).toBeVisible();
  await ui.finishOldEvents();
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.getByText('running', { exact: true })).toBeVisible();
  await expect(page.getByText('old run result', { exact: false })).toHaveCount(0);
  expect(ui.unexpectedRequests).toEqual([]);
});
