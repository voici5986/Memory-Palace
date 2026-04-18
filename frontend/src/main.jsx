import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import RootErrorBoundary, { RootErrorFallback } from './RootErrorBoundary.jsx'
import { primeDocumentLanguageFromBootstrap } from './i18n'
import './index.css'

const UNHANDLED_REJECTION_HANDLER_KEY = '__memory_palace_unhandled_rejection_handler__'

export function registerGlobalUnhandledRejectionHandler(
  target = window,
  onUnhandledRejection = null,
) {
  if (!target?.addEventListener) {
    return null
  }

  const existingHandler = target[UNHANDLED_REJECTION_HANDLER_KEY]
  if (typeof existingHandler === 'function') {
    return existingHandler
  }

  const handler = (event) => {
    event?.preventDefault?.()
    console.error('Unhandled promise rejection', event?.reason ?? event)
    onUnhandledRejection?.(event)
  }

  target.addEventListener('unhandledrejection', handler)
  target[UNHANDLED_REJECTION_HANDLER_KEY] = handler
  return handler
}

primeDocumentLanguageFromBootstrap()

const root = ReactDOM.createRoot(document.getElementById('root'))

const renderRoot = (node) => {
  root.render(
    <React.StrictMode>
      {node}
    </React.StrictMode>,
  )
}

if (typeof window !== 'undefined') {
  registerGlobalUnhandledRejectionHandler(window, () => {
    renderRoot(<RootErrorFallback />)
  })
}

renderRoot(
  <RootErrorBoundary>
    <App />
  </RootErrorBoundary>
)
