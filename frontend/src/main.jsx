import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import RootErrorBoundary from './RootErrorBoundary.jsx'
import { primeDocumentLanguageFromBootstrap } from './i18n'
import './index.css'

primeDocumentLanguageFromBootstrap()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RootErrorBoundary>
      <App />
    </RootErrorBoundary>
  </React.StrictMode>,
)
