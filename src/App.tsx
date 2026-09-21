import { useState } from 'react';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Stats from './components/Stats';
import Features from './components/Features';
import AgencyMatrix from './components/AgencyMatrix';
import SetupGuide from './components/SetupGuide';
import Footer from './components/Footer';
import CanvaView from './components/CanvaView';

function App() {
  const [activeProject, setActiveProject] = useState('metadata');

  return (
    <div className="flex flex-col min-h-screen">
      <Navbar activeProject={activeProject} setActiveProject={setActiveProject} />
      <main>
        {activeProject === 'metadata' ? (
          <div className="animate-in fade-in duration-500">
            <Hero />
            <Stats />
            <Features />
            <AgencyMatrix />
            <SetupGuide />
          </div>
        ) : (
          <CanvaView />
        )}
      </main>
      <Footer />
    </div>
  );
}

export default App;