import { Routes, Route } from 'react-router-dom';
import AppShell from './components/AppShell';
import InputHero from './components/InputHero';
import ResultView from './components/ResultView';
import SharedItineraryView from './components/SharedItineraryView';
import PrivacyPage from './components/PrivacyPage';
import TermsPage from './components/TermsPage';
import JournalLanding from './components/JournalLanding';
import JournalPostView from './components/JournalPostView';
import JournalEditor from './components/JournalEditor';
import JournalMine from './components/JournalMine';
import AuthCallback from './components/AuthCallback';
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
        <Route path="/journal" element={<JournalLanding />} />
        <Route path="/journal/p/:postId" element={<JournalPostView />} />
        <Route path="/journal/new" element={<JournalEditor />} />
        <Route path="/journal/me" element={<JournalMine />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/terms" element={<TermsPage />} />
      </Routes>
    </AppShell>
  );
}
