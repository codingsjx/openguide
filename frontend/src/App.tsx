import HomePage from './pages/HomePage'
import { ContributionSessionProvider } from './components/ContributionSession'

export default function App() {
  return <ContributionSessionProvider><HomePage /></ContributionSessionProvider>
}
