import React from 'react'

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
      return (
        <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 py-10">
          <section
            role="alert"
            className="w-full max-w-xl rounded-3xl border border-white/10 bg-white/95 p-8 text-slate-900 shadow-2xl"
          >
            <p className="text-sm font-semibold uppercase tracking-[0.28em] text-amber-700">
              Memory Palace
            </p>
            <h1 className="mt-4 text-3xl font-semibold text-slate-950">
              Something went wrong.
            </h1>
            <p className="mt-3 text-base leading-7 text-slate-600">
              Please refresh the page and try again.
            </p>
          </section>
        </main>
      )
    }

    return this.props.children
  }
}
