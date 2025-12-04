/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

export default function CommunityPage() {
  return (
    <div className="h-full flex items-center justify-center p-6 bg-gray-50 dark:bg-background-dark">
      <div className="max-w-2xl w-full text-center">
        {/* Icon */}
        <div className="w-24 h-24 mx-auto mb-6 rounded-2xl bg-primary/10 flex items-center justify-center">
          <span className="material-symbols-outlined text-6xl text-primary">groups</span>
        </div>

        {/* Heading */}
        <h1 className="text-3xl font-bold mb-4" style={{ color: 'var(--color-text-primary)' }}>
          Community Page Coming Soon
        </h1>

        {/* Description */}
        <p className="text-lg mb-8" style={{ color: 'var(--color-text-muted)' }}>
          We're building a space for the LangConfig community to share workflows, articles, and best practices.
        </p>

        {/* Features List */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left max-w-xl mx-auto">
          <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-primary flex-shrink-0">article</span>
              <div>
                <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--color-text-primary)' }}>
                  Community Articles
                </h3>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Share tutorials, guides, and insights
                </p>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-primary flex-shrink-0">share</span>
              <div>
                <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--color-text-primary)' }}>
                  Workflow Templates
                </h3>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Discover and share agent workflows
                </p>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-primary flex-shrink-0">forum</span>
              <div>
                <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--color-text-primary)' }}>
                  Discussions
                </h3>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Ask questions and help others
                </p>
              </div>
            </div>
          </div>

          <div className="p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-white dark:bg-panel-dark">
            <div className="flex items-start gap-3">
              <span className="material-symbols-outlined text-primary flex-shrink-0">code</span>
              <div>
                <h3 className="font-semibold text-sm mb-1" style={{ color: 'var(--color-text-primary)' }}>
                  Code Examples
                </h3>
                <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                  Browse community code snippets
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Call to Action */}
        <div className="mt-10 p-4 rounded-lg border border-blue-200 dark:border-blue-500/30 bg-blue-50 dark:bg-blue-500/10">
          <p className="text-sm text-blue-800 dark:text-blue-300">
            <strong>Want to contribute?</strong> Stay tuned for updates on how you can share your knowledge with the community.
          </p>
        </div>
      </div>
    </div>
  );
}
