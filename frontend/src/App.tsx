import { Routes, Route } from 'react-router-dom';
import AppShell from './components/AppShell';
import InputHero from './components/InputHero';
import ResultView from './components/ResultView';
import SharedItineraryView from './components/SharedItineraryView';
import PrivacyPage from './components/PrivacyPage';
import TermsPage from './components/TermsPage';
import { usePlanning } from './hooks/use-planning';

export default function App() {
  const planning = usePlanning();

  return (
    <AppShell onNewDay={planning.reset} showBack={planning.state !== 'idle'}>
      <Routes>
        <Route
          path="/"
          element={
            planning.state === 'idle' ? (
              <InputHero onSubmit={planning.submit} />
            ) : planning.state === 'loading' ? (
              <InputHero onSubmit={planning.submit} loading />
            ) : planning.state === 'error' ? (
              <InputHero
                onSubmit={planning.submit}
                error={planning.error}
              />
            ) : (
              <ResultView
                result={planning.result}
                onNewDay={planning.reset}
              />
            )
          }
        />
        <Route path="/r/:shareId" element={<SharedItineraryView />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
      </Routes>
    </AppShell>
  );
}
