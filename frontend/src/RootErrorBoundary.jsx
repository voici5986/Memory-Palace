import React from 'react'
import i18n from './i18n'

export function RootErrorFallback() {
  const appName = i18n.t('common.appName')
  const title = i18n.t('app.errorBoundary.title')
  const message = i18n.t('app.errorBoundary.message')
  const refreshLabel = i18n.t('common.actions.refresh')

  const handleRefresh = () => {
    if (typeof window === 'undefined') return
    window.location?.reload?.()
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 py-10">
      <section
        role="alert"
        className="w-full max-w-xl rounded-3xl border border-white/10 bg-white/95 p-8 text-slate-900 shadow-2xl"
      >
        <p className="text-sm font-semibold uppercase tracking-[0.28em] text-amber-700">
          {appName}
        </p>
        <h1 className="mt-4 text-3xl font-semibold text-slate-950">
          {title}
        </h1>
        <p className="mt-3 text-base leading-7 text-slate-600">
          {message}
        </p>
        <button
          type="button"
          onClick={handleRefresh}
          className="mt-6 inline-flex items-center rounded-full bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400/60"
        >
          {refreshLabel}
        </button>
      </section>
    </main>
  )
}

export default class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return <RootErrorFallback />
    }

    return this.props.children
  }
}
